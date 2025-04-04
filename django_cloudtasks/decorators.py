# decorators.py

import os
import logging
import inspect
from functools import wraps
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)

# Task registry to maintain tasks logic and their parameter names.
TASKS_REGISTRY = {}

def register_task(func):
    """
    Decorator to register function as runnable Cloud Task.
    """
    task_name = func.__name__
    signature = inspect.signature(func)
    param_names = list(signature.parameters.keys())

    TASKS_REGISTRY[task_name] = {
        "func": func,
        "param_names": param_names,
    }

    logger.info(f"Registered Task: {task_name} with params: {param_names}")

    @wraps(func)
    def wrapper(data):
        kwargs = {k: data[k] for k in param_names if k in data}
        return func(**kwargs)

    return wrapper

def authenticate_task(view_func):
    """
    Decorator to authenticate incoming Cloud Tasks requests using Bearer token.
    """
    TASKAPP_AUTH_TOKEN = os.getenv("TASKAPP_AUTH_TOKEN", "")

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return HttpResponseForbidden("Missing Authorization Header.")

        token = auth.split("Bearer ")[-1].strip()
        if token != TASKAPP_AUTH_TOKEN:
            return HttpResponseForbidden("Invalid Token.")

        return view_func(request, *args, **kwargs)

    return wrapped