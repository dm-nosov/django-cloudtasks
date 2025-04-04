# urls.py

from django.urls import path
from .views import revoke_view, task_dispatcher, tracker_view



urlpatterns = [
    # Execute registered tasks by name from Google Cloud Tasks
    path('run/<str:task_name>/', task_dispatcher, name='cloudtasks_dynamic_run'),

    # Track and process results after task execution
    path('tracker/', tracker_view, name='cloudtasks_tracker'),

    # Revoke scheduled tasks or chains dynamically
    path('revoke/', revoke_view, name='cloudtasks_revoke'),
]