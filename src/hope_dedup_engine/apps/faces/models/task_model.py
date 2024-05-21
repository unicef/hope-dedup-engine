from django.db import models
from django.utils.translation import gettext_lazy as _


class TaskModel(models.Model):
    class StatusChoices(models.TextChoices):
        PROCESSING = "PROCESSING", _("Processing")
        COMPLETED_SUCCESS = "COMPLETED_SUCCESS", _("Completed Successfully")
        FAILED = "FAILED", _("Failed")

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
