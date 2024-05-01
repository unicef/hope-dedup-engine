import logging

from django.utils import timezone

from celery import shared_task

from hope_dedup_engine.apps.faces.models import TaskModel

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def deduplicate(self):
    logger.info("Deduplication task started")
    task: TaskModel = None
    try:
        print(f"{self.request=}")
        task = TaskModel.objects.create(
            name="Deduplication",
            celery_task_id=self.request.id,
        )
        long_running_task()
        task.status = TaskModel.StatusChoices.COMPLETED_SUCCESS
        task.completed_at = timezone.now()
        task.is_success = True
    except Exception as e:
        logger.exception("Deduplication task failed", exc_info=e)
        if task:
            task.status = TaskModel.StatusChoices.FAILED
            task.completed_at = timezone.now()
            task.is_success = False
            task.error = str(e)
    finally:
        if task:
            task.save(update_fields=["status", "completed_at", "is_success", "error"])
        logger.info("Deduplication task ended")


def long_running_task() -> bool:
    logger.info("Long running task started")
    import time

    time.sleep(10)
    # raise Exception('Something went wrong')
    logger.info("Long running task completed")
    return True
