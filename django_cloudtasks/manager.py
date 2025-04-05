# manager.py

import logging
from typing import Dict, List, Optional, Any, TypeVar

import os
from django.urls import reverse

from django_cloudtasks.utils import schedule_cloud_task

from .models import CloudChain, CloudTask, TaskStatus
from .decorators import TASKS_REGISTRY

logger = logging.getLogger(__name__)

T = TypeVar('T', bound='CloudChainManager')


class CloudChainManager:
    """
    Core class for creating and managing task chains and groups.
    """

    def __init__(self, chain=None):
        self.chain = chain or CloudChain.objects.create()
        self.last_task = None

    def add_task(self, endpoint_path: str, payload: Optional[Dict[str, Any]] = None, 
                 delay_seconds: int = 0, error_callback: Optional[str] = None) -> T:
        """
        Add a single task to the chain.
        
        Args:
            endpoint_path: The name of the task to execute
            payload: Dictionary of parameters to pass to the task
            delay_seconds: Number of seconds to delay execution
            error_callback: Optional name of task to call if this task fails
            
        Returns:
            Self for method chaining
        """
        task = CloudTask.objects.create(
            chain=self.chain,
            endpoint_path=reverse("cloudtasks_dynamic_run", args=[endpoint_path]),
            payload=payload or {},
            delay_seconds=delay_seconds,
            parent=self.last_task if self.last_task and not self.last_task.is_group else None
        )

        if error_callback:
            task.payload['_error_callback'] = error_callback
            task.save()

        # If previous task was a group marker, explicitly link this as next_task
        if self.last_task and self.last_task.is_group and not self.last_task.next_task:
            self.last_task.next_task = task
            self.last_task.save()

        self.last_task = task
        return self

    def add_group(self, tasks_info: List[Dict[str, Any]], 
                  error_callback: Optional[str] = None) -> T:
        """
        Add a group of tasks to be executed in parallel.
        
        Args:
            tasks_info: List of dictionaries with task configurations
                Each dict should have 'endpoint_path' and optionally 'payload' and 'delay_seconds'
            error_callback: Optional name of task to call if any task in the group fails
            
        Returns:
            Self for method chaining
        """
        group_marker = CloudTask.objects.create(
            chain=self.chain,
            is_group=True,
            parent=self.last_task
        )

        if error_callback:
            group_marker.payload['_error_callback'] = error_callback
            group_marker.save()

        for task_info in tasks_info:
            CloudTask.objects.create(
                chain=self.chain,
                endpoint_path=reverse("cloudtasks_dynamic_run", args=[task_info["endpoint_path"]]),
                payload=task_info.get("payload", {}),
                delay_seconds=task_info.get("delay_seconds", 0),
                parent=group_marker
            )

        self.last_task = group_marker
        return self
    
    def add_chain(self, chain_manager: 'CloudChainManager') -> T:
        """
        Add an entire chain to execute after the current chain completes.
        
        Args:
            chain_manager: Another CloudChainManager instance to be executed after this one
            
        Returns:
            Self for method chaining
        """
        chain_to_add = chain_manager.chain
        chain_to_add.parent_chain = self.chain
        chain_to_add.save()
        return self

    def add_chain_group(self, *chain_managers: 'CloudChainManager') -> T:
        """
        Execute multiple chains in parallel, then continue afterwards.
        
        Args:
            *chain_managers: Variable number of CloudChainManager instances to execute in parallel
            
        Returns:
            Self for method chaining
        """
        group_marker_task = CloudTask.objects.create(
            chain=self.chain,
            is_group=True,
            parent=self.last_task
        )

        for cmgr in chain_managers:
            cmgr.chain.parent_chain = self.chain
            cmgr.chain.save()

            cmgr_root_tasks = CloudTask.objects.filter(chain=cmgr.chain, parent__isnull=True)
            for root_task in cmgr_root_tasks:
                root_task.parent = group_marker_task
                root_task.save()

        self.last_task = group_marker_task
        return self

    def run(self):
        """
        Schedule only root tasks with no parent and no preceding group.
        Group-related tasks' next_task is scheduled via tracker after group completion.
        """
        root_tasks = CloudTask.objects.filter(
            chain=self.chain,
            parent__isnull=True, 
            status=TaskStatus.PENDING
        ).exclude(  # Explicitly EXCLUDE any tasks pointed to by group's next_task
            id__in=CloudTask.objects.filter(next_task__isnull=False).values_list('next_task', flat=True)
        )

        for task in root_tasks:
            schedule_cloud_task(task)


