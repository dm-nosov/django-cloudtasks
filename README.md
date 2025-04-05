# README.md

## Django Cloud Tasks

A Django library for managing asynchronous tasks and complex workflows, built on top of Google Cloud Tasks. This library allows you to schedule tasks, chains, parallel execution (groups), set error callbacks, apply delays, and handle revocations cleanly and explicitly.

---

## Key Features

- **Task**: Single asynchronous units of execution.
- **Chain**: Sequences of tasks that run one after another.
- **Group**: Multiple parallel tasks whose results are aggregated upon completion.
- **Sub-Chains**: Chains triggered by completion of a parent chain.
- **Delayed Tasks**: Schedule execution for a specific future time.
- **Error Callbacks**: Define handlers for unexpected errors.
- **Result Injection**: Automatically passes previous outputs into next tasks.
- **Revocation**: Dynamically cancel executing or future tasks.

---

## Installation and Setup

### Requirements  

```bash
pip install django-gcp-cloudtasks
```

### Environment variables required

In your project's `.env` or OS environment set these variables:

```env
TASKAPP_GCP_PROJECT=my-project
TASKAPP_GCP_LOCATION=us-central1
TASKAPP_GCP_QUEUE=default
TASKAPP_CLOUD_RUN_URL=https://YOUR_CLOUD_RUN_ENDPOINT
TASKAPP_AUTH_TOKEN=YOUR_SECURE_AUTH_TOKEN
```

### Django settings

Add `django_cloudtasks` to your `INSTALLED_APPS` in your Django `settings.py`:

```python
INSTALLED_APPS = [
    ...
    'django_cloudtasks',
    ...
]
```

Apply migrations:

```bash
python manage.py migrate django_cloudtasks
```

### URL Configuration

Add the following to your project's `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    ...
    path('cloudtasks/', include('django_cloudtasks.urls')),
    ...
]
```

This will register all the necessary endpoints for task execution, tracking, and revocation.



### Create a Service Account 

1. **Create a Service Account**:
```bash
gcloud iam service-accounts create my-service-account \
    --display-name="My Service Account"
```

2. **Grant Roles to the Service Account**:
   - Grant permissions to interact with Cloud Tasks and other necessary services.

```bash
gcloud projects add-iam-policy-binding test-project-455815 \
    --member="serviceAccount:my-service-account@test-project-455815.iam.gserviceaccount.com" \
    --role="roles/cloudtasks.enqueuer"
```

   - You may need additional roles depending on your use case, e.g., `roles/cloudtasks.viewer`.

3. **Generate a Key for the Service Account**:
```bash
gcloud iam service-accounts keys create ~/path/to/key.json \
    --iam-account=my-service-account@test-project-455815.iam.gserviceaccount.com
```

### Set Up Environment Variable

Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the path of your service account key file:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="~/path/to/key.json"
```



---

## Usage Examples

### Single Task

```python
from django_cloudtasks.decorators import register_task

@register_task
def sum(a, b):
    return a + b

from django_cloudtasks.manager import CloudChainManager

chain_mgr = CloudChainManager()
chain_mgr.add_task("sum", {"a": 4, "b": 5})
chain_mgr.run()
```

---

### Sequential Tasks (Chain)

```python
from django_cloudtasks.manager import CloudChainManager

chain_mgr = CloudChainManager()
chain_mgr.add_task("sum", {"a": 4, "b": 5})
chain_mgr.add_task("sum", {"b": 10})  # auto-inject result from previous task into 'a'
chain_mgr.run()
```

---

### Group Tasks (Parallel)

```python
from django_cloudtasks.manager import CloudChainManager

chain_mgr = CloudChainManager()

chain_mgr.add_group([
    {"endpoint_path": "sum", "payload": {"a": 3, "b": 3}},
    {"endpoint_path": "sum", "payload": {"a": 7, "b": 2}}
])

chain_mgr.add_task("sum", {"a": 4, "b": 5}, delay_seconds=30)

chain_mgr.run()
```

---

### Using Delays

```python
from django_cloudtasks.manager import CloudChainManager

chain_mgr = CloudChainManager()
chain_mgr.add_task("sum", {"a": 2, "b": 1}, delay_seconds=300)
chain_mgr.run()
```
Delays execution for 5 minutes (300 seconds).

---

### Error Callbacks

Automatically schedule another task if any error occurs:

```python
from django_cloudtasks.manager import CloudChainManager
from django_cloudtasks.decorators import register_task

@register_task
def faulty_task(a, b):
    # Always raise an exception to simulate failure:
    raise ValueError(f"Test error: inputs {a}, {b}")

@register_task
def my_error_handler(original_task_id, original_task_name, error, payload):
    print(f"Error callback triggered for task {original_task_name} id={original_task_id}")
    print(f"Error was: {error}")
    print(f"Payload that caused failure: {payload}")


chain_mgr = CloudChainManager()
chain_mgr.add_task(
    "faulty_task", {"a": 1, "b": 2}, error_callback="my_error_handler"
)
chain_mgr.run()
```

#### Error Handler Parameters

Error handlers must accept the following parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `original_task_id` | UUID | The unique identifier of the task that failed |
| `original_task_name` | str | The name/endpoint of the task that failed |
| `error` | str | String representation of the exception that occurred |
| `payload` | dict | The original payload sent to the task that failed |

### CloudChainManager Structure

The `CloudChainManager` class provides properties and methods to access task and chain IDs for monitoring, debugging, or revocation:

```python
from django_cloudtasks.manager import CloudChainManager

# Create a chain manager
chain_mgr = CloudChainManager()
chain_mgr.add_task("task1", {"a": 1})
chain_mgr.add_task("task2", {"b": 2})

# Access chain ID for revocation
chain_id = chain_mgr.chain.id  # UUID of the entire chain
print(f"Chain ID: {chain_id}")

# Access the last added task's ID
last_task_id = chain_mgr.last_task.id  # UUID of the most recently added task
print(f"Last Task ID: {last_task_id}")

# Get all tasks in the chain
all_tasks = chain_mgr.chain.tasks.all()
for task in all_tasks:
    print(f"Task ID: {task.id}, Endpoint: {task.endpoint_path}")

# Revoke the chain
from django_cloudtasks.utils import revoke_chain
revoke_chain(chain_id)

# Revoke a specific task
from django_cloudtasks.utils import revoke_task
revoke_task(last_task_id)
```

### Chaining and Grouping Chains

Automatically schedule another task if any error occurs:

```python

from django_cloudtasks.manager import CloudChainManager
c1 = CloudChainManager()
c1.add_task("sum", {"a": 4, "b": 5})

c2 = CloudChainManager()
c2.add_task("sum", {"a": 2, "b": 5})

c3 = CloudChainManager()
c3.add_chain_group(c1, c2)
c3.run()

```

---

### Revoking Tasks and Chains

Revoke actively scheduled or running tasks:

API Endpoint:  
```
GET /cloudtasks/revoke/?task=<TASK_ID>
GET /cloudtasks/revoke/?chain=<CHAIN_ID>
```

---

## Provided endpoints

| Endpoint | Usage | Description |
| -------- | ----- | ----------- |
| `/cloudtasks/run/<task_name>/` | POST | Execute a registered task (Cloud Tasks entrypoint) |
| `/cloudtasks/tracker/` | POST | Receive results and control flow after tasks execution |
| `/cloudtasks/revoke/` | GET | Revoke specific tasks or entire chains |