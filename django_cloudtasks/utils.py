import logging
from django_cloudtasks.constants import PROJECT_ID, LOCATION_ID, QUEUE_ID, CLOUD_RUN_URL, AUTH_TOKEN, ChainStatus, TaskStatus
from django_cloudtasks.decorators import TASKS_REGISTRY
from django_cloudtasks.models import CloudChain, CloudTask
import datetime
import json
from google.cloud import tasks_v2
from google.protobuf.timestamp_pb2 import Timestamp

logger = logging.getLogger(__name__)


def inject_result_into_next_task(task, result):
    if not result:
        logger.warning(f"No result to inject into task {task.id}. Skipping injection.")
        return

    endpoint = task.endpoint_path.strip("/").split("/")[-1]
    task_meta = TASKS_REGISTRY.get(endpoint)

    if task_meta:
        missing_params = [param for param in task_meta["param_names"] if param not in task.payload]
        if len(missing_params) == 1:
            missing_param = missing_params[0]
            task.payload[missing_param] = result
            task.save()
            logger.info(f"Injected result into task {task.id} for param '{missing_param}': {result}")
        else:
            logger.warning(f"Expected exactly one missing param for injection into task {task.id}, found {missing_params}. No injection done.")
    else:
        logger.warning(f"Task logic '{endpoint}' not found in TASKS_REGISTRY. Check registration.")

def schedule_cloud_task(task):
    if task.status != TaskStatus.PENDING:
        logger.warning(f"Task {task.id} is {task.status}. Skipping scheduling.")
        return
    
    if task.is_group:
        # Correct behavior: Schedule children, not marker
        child_tasks = task.children.filter(status=TaskStatus.PENDING)
        if not child_tasks.exists():
            logger.warning(f"Group task {task.id} has no child tasks to schedule.")
            return
        for child in child_tasks:
            schedule_cloud_task(child)
        task.status = TaskStatus.SCHEDULED
        task.save()
        logger.info(f"Scheduled all children tasks inside group {task.id}.")
        return

    # existing scheduling logic follows (unchanged):
    client = tasks_v2.CloudTasksClient()
    queue_path = client.queue_path(PROJECT_ID, LOCATION_ID, QUEUE_ID)

    payload = task.payload.copy()
    payload['_task_id'] = str(task.id)

    task_body = {
        'http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'url': f"{CLOUD_RUN_URL}{task.endpoint_path}",
            'headers': {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {AUTH_TOKEN}",
            },
            'body': json.dumps(payload).encode(),
        }
    }

    if task.delay_seconds:
        schedule_time = Timestamp()
        schedule_time.FromDatetime(datetime.datetime.utcnow() + datetime.timedelta(seconds=task.delay_seconds))
        task_body['schedule_time'] = schedule_time

    response = client.create_task(parent=queue_path, task=task_body)
    task.external_task_name = response.name
    task.status = TaskStatus.SCHEDULED
    task.save()
    logger.info(f"Scheduled task {task.id}: Cloud Task Name = {response.name}")


def revoke_task(task_id):
    """
    Revoke (cancel) a specific task from Google Cloud Tasks and mark as revoked in DB.
    """
    try:
        task = CloudTask.objects.get(id=task_id)
        if task.external_task_name:
            client = tasks_v2.CloudTasksClient()
            client.delete_task(name=task.external_task_name)
            logger.info(f"Revoked external task {task.external_task_name}")

        task.status = TaskStatus.REVOKED
        task.save()
        logger.info(f"Marked task {task.id} as REVOKED.")
        
        # Explicitly update Chain status:
        chain = task.chain
        if chain.status not in [ChainStatus.FAILED, ChainStatus.SUCCESS]:
            chain.status = ChainStatus.FAILED
            chain.save()
            logger.info(f"Chain {chain.id} marked as FAILED due to task revocation.")

        return True

    except CloudTask.DoesNotExist:
        logger.error(f"Task {task_id} does not exist for revocation.")
        return False


def revoke_chain(chain_id):
    """
    Revoke (cancel) all tasks within a specific chain.
    """
    try:
        chain = CloudChain.objects.get(id=chain_id)

        for task in chain.tasks.filter(status__in=[TaskStatus.PENDING, TaskStatus.SCHEDULED]):
            revoke_task(task.id)

        chain.status = ChainStatus.FAILED
        chain.save()

        logger.info(f"Chain {chain.id} was revoked.")
        return True

    except CloudChain.DoesNotExist:
        logger.error(f"Chain {chain_id} does not exist for revocation.")
        return False
    
    
def trigger_subchain(parent_chain, previous_result=None):
    """
    Trigger next chains linked via parent_chain if they're ready.
    """
    subchains = CloudChain.objects.filter(parent_chain=parent_chain)
    for subchain in subchains:
        if subchain.status == ChainStatus.PENDING:
            root_tasks = CloudTask.objects.filter(chain=subchain, parent__isnull=True)
            
            for task in root_tasks:
                inject_result_into_next_task(task, previous_result)
                schedule_cloud_task(task)

def trigger_parent_chain_check(chain):
    """
    Recursively propagate status updates upwards in chains-of-chains.
    """
    chain = CloudChain.objects.select_for_update().get(id=chain.id)

    child_chains = CloudChain.objects.filter(parent_chain=chain)
    chain_updated = False

    if child_chains.exists():
        if all(c.status == ChainStatus.SUCCESS for c in child_chains):
            chain.status = ChainStatus.SUCCESS
            chain.result = [c.result for c in child_chains]
            chain.save()
            chain_updated = True
            logger.info(f"Chain {chain.id} marked SUCCESS due to successful child chains.")

        elif any(c.status == ChainStatus.FAILED for c in child_chains):
            chain.status = ChainStatus.FAILED
            chain.save()
            chain_updated = True
            logger.warning(f"Chain {chain.id} marked FAILED due to failed child chains.")

        # Recursive upward propagation
        if chain_updated and chain.parent_chain:
            trigger_parent_chain_check(chain.parent_chain)

def run_error_callback(task_id, task_name, original_payload, exception):
    """
    Clearly executes the error callback immediately using TASKS_REGISTRY.
    """
    try:
        task_obj = CloudTask.objects.get(id=task_id)
        error_callback_name = task_obj.payload.get('_error_callback')
        
        if not error_callback_name:
            logger.warning(f"No error callback defined for task '{task_name}' (id: {task_id}).")
            return

        callback_meta = TASKS_REGISTRY.get(error_callback_name)
        if not callback_meta:
            logger.error(f"Error callback task '{error_callback_name}' not found in TASKS_REGISTRY.")
            return

        callback_func = callback_meta['func']
        # explicitly call error callback function (no roundtrip):
        callback_payload = {
            "original_task_id": task_id,
            "original_task_name": task_name,
            "error": str(exception),
            "payload": original_payload
        }
        
        logger.info(f"Executing error callback '{error_callback_name}' for failed task {task_id}")
        callback_func(**callback_payload)

    except Exception as e:
        logger.exception(f"Critical failure executing error callback for task {task_id}: {e}")