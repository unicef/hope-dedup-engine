from django.db import models

from model_utils.models import UUIDModel


class TaskModel(UUIDModel):
    class StatusChoices(models.TextChoices):
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED_SUCCESS = "COMPLETED_SUCCESS", "Completed Successfully"
        FAILED = "FAILED", "Failed"

    name = models.CharField(max_length=100)
    celery_task_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PROCESSING)
    is_success = models.BooleanField(default=False)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.status} - {self.created_at} - {self.completed_at}"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Task"
