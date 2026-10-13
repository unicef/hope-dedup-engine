"""Schedule the daily deletion of rejected biographic documents.

Beat reads its schedule from the database, so the task has to exist as a row.
`get_or_create` keeps a re-run harmless; the reverse removes the task but leaves
the crontab, which other tasks may share.
"""

from django.db import migrations

from hope_dedup_engine.apps.biographic.const import CLEANUP_REJECTED_PERIODIC_TASK_NAME, CLEANUP_REJECTED_TASK

CLEANUP_HOUR = "2"
CLEANUP_QUEUE = "queue_hde"


def create_periodic_task(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour=CLEANUP_HOUR,
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )
    PeriodicTask.objects.get_or_create(
        name=CLEANUP_REJECTED_PERIODIC_TASK_NAME,
        defaults={
            "task": CLEANUP_REJECTED_TASK,
            "crontab": schedule,
            "queue": CLEANUP_QUEUE,
            "description": "Delete documents of rejected and canceled biographic sets from Elasticsearch.",
        },
    )


def delete_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=CLEANUP_REJECTED_PERIODIC_TASK_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("biographic", "0003_biographicjob_set_notifications_and_log"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, delete_periodic_task),
    ]
