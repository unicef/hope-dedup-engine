from django.db import models


class DeduplicationTask(models.Model):
    task_id = models.UUIDField(primary_key=True)
    status = models.CharField(
        max_length=20, choices=[("PENDING", "Pending"), ("COMPLETED", "Completed"), ("FAILED", "Failed")]
    )
    created_at = models.DateTimeField(auto_now_add=True)


class DeduplicationResult(models.Model):
    task = models.ForeignKey(DeduplicationTask, on_delete=models.CASCADE)
    uuid1 = models.UUIDField()
    uuid2 = models.UUIDField()
    similarity_score = models.FloatField()
