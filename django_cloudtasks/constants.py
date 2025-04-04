# constants.py

import os

PROJECT_ID = os.getenv("TASKAPP_GCP_PROJECT")
LOCATION_ID = os.getenv("TASKAPP_GCP_LOCATION")
QUEUE_ID = os.getenv("TASKAPP_GCP_QUEUE")
CLOUD_RUN_URL = os.getenv("TASKAPP_CLOUD_RUN_URL")
AUTH_TOKEN = os.getenv("TASKAPP_AUTH_TOKEN")

MAX_TASK_RETRIES = 2

class ChainStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

    CHOICES = [
        (PENDING, "Pending"),
        (RUNNING, "Running"),
        (SUCCESS, "Success"),
        (FAILED, "Failed"),
    ]


class TaskStatus:
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ERROR = "ERROR"
    REVOKED = "REVOKED"

    CHOICES = [
        (PENDING, "Pending"),
        (SCHEDULED, "Scheduled"),
        (SUCCESS, "Success"),
        (FAILED, "Failed"),
        (ERROR, "Error"),
        (REVOKED, "Revoked"),
    ]