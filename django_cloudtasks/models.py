# models.py

import uuid
from django.db import models
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from .constants import ChainStatus, TaskStatus


class CloudChain(models.Model):
    """
    Represents a chain with tasks executed sequentially or in parallel.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(
        max_length=20, 
        choices=ChainStatus.CHOICES, 
        default=ChainStatus.PENDING
    )
    result = models.JSONField(
        null=True, blank=True, encoder=DjangoJSONEncoder, default=None
    )
    parent_chain = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CloudChain({self.id}, status={self.status})"


class CloudTask(models.Model):
    """
    Single executable task or group of parallel tasks.
    Threads a chain via `parent` field.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chain = models.ForeignKey(
        CloudChain,
        related_name="tasks",
        on_delete=models.CASCADE
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.SET_NULL
    )

    # Task details
    endpoint_path = models.CharField(max_length=255, blank=True, null=True)
    payload = models.JSONField(default=dict, encoder=DjangoJSONEncoder)
    delay_seconds = models.PositiveIntegerField(default=0)

    # Group task marker
    is_group = models.BooleanField(default=False)
    
    # Explicit next task after completing all children tasks (used by groups)
    next_task = models.ForeignKey(
        "self", null=True, blank=True, related_name="+", on_delete=models.SET_NULL
    )

    status = models.CharField(
        max_length=20,
        choices=TaskStatus.CHOICES,
        default=TaskStatus.PENDING
    )
    execution_result = models.JSONField(
        null=True, blank=True, encoder=DjangoJSONEncoder
    )
    external_task_name = models.CharField(
        max_length=500, null=True, blank=True,
        help_text="Google Cloud Tasks service task name for revocation management."
    )
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        task_type = "Group Marker" if self.is_group else f"Task({self.endpoint_path})"
        return f"{task_type}[{self.id}]: {self.status}"

