# Generated by Django 4.2.11 on 2024-05-01 12:14

from django.db import migrations, models
import model_utils.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TaskModel",
            fields=[
                (
                    "id",
                    model_utils.fields.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=100)),
                ("celery_task_id", models.UUIDField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PROCESSING", "Processing"),
                            ("COMPLETED_SUCCESS", "Completed Successfully"),
                            ("FAILED", "Failed"),
                        ],
                        default="PROCESSING",
                        max_length=20,
                    ),
                ),
                ("is_success", models.BooleanField(default=False)),
                ("error", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Task",
                "ordering": ["-created_at"],
            },
        ),
    ]
