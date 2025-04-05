# views.py

import json
import logging
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.db import transaction

from django_cloudtasks.constants import AUTH_TOKEN, CLOUD_RUN_URL, MAX_TASK_RETRIES, ChainStatus, TaskStatus

from .models import CloudChain, CloudTask, TaskStatus
from .decorators import authenticate_task, TASKS_REGISTRY
from .utils import inject_result_into_next_task, revoke_chain, revoke_task, run_error_callback, schedule_cloud_task, trigger_parent_chain_check, trigger_subchain

logger = logging.getLogger(__name__)

@csrf_exempt
@authenticate_task
def task_dispatcher(request, task_name):
    """
    Execute the registered cloud task and report back to tracker.
    """

    # CLEARLY LOG ALL HEADERS
    headers = dict(request.headers)
    logger.info(f"☑️ All incoming headers clearly logged for debugging: {headers}")

    execution_count = int(request.headers.get('X-CloudTasks-TaskExecutionCount', '0'))
    retry_count = int(request.headers.get('X-CloudTasks-TaskRetryCount', '0'))

    # Explicitly log Google Cloud Tasks retry headers clearly
    logger.info(f"⚙️ Retry headers received: ExecutionCount={execution_count}, RetryCount={retry_count}")

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    data = json.loads(request.body)
    task_id = data.get("_task_id")

    if task_name not in TASKS_REGISTRY:
        return JsonResponse({"error": f"No task '{task_name}' registered."}, status=404)

    task_meta = TASKS_REGISTRY[task_name]
    logger.info(f"Executing task '{task_name}' (id={task_id}) with payload: {data}")

    kwargs = {k: data[k] for k in task_meta['param_names'] if k in data}

    try:
        result = task_meta['func'](**kwargs)
        report_task_results(task_id=task_id, result=result)
        return JsonResponse({"result": result})

    except Exception as ex:
        logger.exception(f"Task '{task_name}' execution error: {ex}")

        retry_count = int(request.headers.get('X-Cloudtasks-Taskretrycount', '0'))

        if retry_count >= MAX_TASK_RETRIES:
            logger.error(f"Max retries exceeded for task {task_id} after {retry_count} tries.")

            # Execute error callback immediately (no extra roundtrip):
            run_error_callback(task_id, task_name, kwargs, ex)

            # Report back permanent failure to tracker explicitly:
            report_task_results(task_id=task_id, error=str(ex))
            return JsonResponse({"error": str(ex), "final_attempt": True}, status=200)

        # Allow retry 
        return JsonResponse({"error": str(ex), "attempt": execution_count}, status=500)



def report_task_results(task_id, result=None, error=None):
    """
    Report task status back to internal tracker endpoint.
    """
    tracker_url = reverse('cloudtasks_tracker')
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    payload = {"_task_id": task_id}
    if error:
        payload["_error"] = error
    else:
        payload["_result"] = result

    try:
        response = requests.post(f"{CLOUD_RUN_URL}{tracker_url}", json=payload, headers=headers)
        logger.info(f"Reported results for {task_id} with status {response.status_code}")

    except requests.RequestException as exc:
        logger.error(f"Error reporting results task {task_id}: {exc}")

@csrf_exempt
@authenticate_task
def tracker_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    data = json.loads(request.body)
    task_id = data.get("_task_id")
    task_result = data.get("_result")
    task_error = data.get("_error")

    logger.info(f"Tracking task {task_id}, result: {task_result}, error: {task_error}")

    try:
        with transaction.atomic():
            # STEP 1: Always update task immediately:
            task = CloudTask.objects.select_for_update().get(id=task_id)
            if task.status not in [TaskStatus.PENDING, TaskStatus.SCHEDULED]:
                logger.warning(f"Task {task_id} already finalized.")
                return JsonResponse({"status": "ignored"})
            
            task.status = TaskStatus.SUCCESS if not task_error else TaskStatus.FAILED
            task.execution_result = task_result if not task_error else {"error": task_error}
            task.save()

            # STEP 2: Immediately schedule next child tasks (sequential execution):
            for child in task.children.filter(status=TaskStatus.PENDING, is_group=False):
                inject_result_into_next_task(child, task.execution_result)
                schedule_cloud_task(child)

            # STEP 3: Explicitly handle group (parallel tasks):
            if task.parent and task.parent.is_group:
                group = CloudTask.objects.select_for_update().get(id=task.parent.id)
                children = group.children.select_for_update()

                if all(c.status == TaskStatus.SUCCESS for c in children):
                    group.status = TaskStatus.SUCCESS
                    group.execution_result = [c.execution_result for c in children]
                    group.save()

                    # Schedule next after group tasks:
                    if group.next_task and group.next_task.status == TaskStatus.PENDING:
                        inject_result_into_next_task(group.next_task, group.execution_result)
                        schedule_cloud_task(group.next_task)

                elif any(c.status in [TaskStatus.FAILED, TaskStatus.REVOKED] for c in children):
                    group.status = TaskStatus.FAILED
                    group.save()

            # STEP 4: Explicitly update chain status only at chain completion:
            chain = CloudChain.objects.select_for_update().get(id=task.chain.id)

            all_chain_tasks = CloudTask.objects.filter(chain=chain, is_group=False)
            chain_updated = False

            # (a) For chains directly containing tasks:
            if all(t.status == TaskStatus.SUCCESS for t in all_chain_tasks):
                chain.status = ChainStatus.SUCCESS
                chain.result = [t.execution_result for t in all_chain_tasks]
                chain.save()
                chain_updated = True

            elif any(t.status == TaskStatus.FAILED for t in all_chain_tasks):
                chain.status = ChainStatus.FAILED
                chain.save()
                chain_updated = True

            # (b) For chains containing sub-chains, explicitly considered:
            child_chains = CloudChain.objects.filter(parent_chain=chain)
            if child_chains.exists():
                if all(c.status == ChainStatus.SUCCESS for c in child_chains):
                    chain.status = ChainStatus.SUCCESS
                    chain.result = [c.result for c in child_chains]
                    chain.save()
                    chain_updated = True

                elif any(c.status == ChainStatus.FAILED for c in child_chains):
                    chain.status = ChainStatus.FAILED
                    chain.save()
                    chain_updated = True

            # Explicitly trigger child chains DOWNWARD first
            if chain_updated and chain.status == ChainStatus.SUCCESS:
                # ✨ Explicitly trigger subchains (next chains) after this chain succeeded clearly:
                trigger_subchain(chain, previous_result=chain.result)
                
            # STEP 5: Propagate upwards recursively (chains-of-chains only at completion):
            if chain_updated and chain.parent_chain:
                trigger_parent_chain_check(chain.parent_chain)

        return JsonResponse({"status": "tracked"})

    except CloudTask.DoesNotExist:
        logger.error(f"task {task_id} does not exist")
        return JsonResponse({"error": "task missing"}, status=404)
    except Exception as ex:
        logger.exception(f"Tracker critical failure: {ex}")
        return JsonResponse({"error": str(ex)}, status=500)
    
    
@authenticate_task
def revoke_view(request):
    """
    Endpoint to revoke scheduled tasks or entire chains.
    Usage:
    GET /cloudtasks/revoke/?task=<TASK_ID>
    GET /cloudtasks/revoke/?chain=<CHAIN_ID>
    """
    task_id = request.GET.get('task')
    chain_id = request.GET.get('chain')

    if task_id:
        success = revoke_task(task_id)
        return JsonResponse({"task_id": task_id, "revoked": success})

    if chain_id:
        success = revoke_chain(chain_id)
        return JsonResponse({"chain_id": chain_id, "revoked": success})

    return JsonResponse({"error": "Provide task or chain ID."}, status=400)