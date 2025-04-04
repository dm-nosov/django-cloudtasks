# django-gcp-cloudtasks

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

## Installation

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
python manage.py makemigrations django_cloudtasks
python manage.py migrate django_cloudtasks
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

---

## Structure & further implementation (our files plan)

```
django_cloudtasks/
├── README.md (this file)
├── __init__.py
├── constants.py
├── models.py
├── manager.py
├── decorators.py
├── views.py
├── urls.py
└── utils.py
```