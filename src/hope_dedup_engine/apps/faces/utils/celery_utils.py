import logging
from functools import wraps

from django.utils import timezone

from hope_dedup_engine.apps.faces.models import TaskModel


def task_lifecycle(name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            logger = logging.getLogger(func.__module__)
            logger.info(f"{name} task started")
            task: TaskModel = None
            try:
                task = TaskModel.objects.create(
                    name=name,
                    celery_task_id=self.request.id,
                )

                result = func(self, *args, **kwargs)

                task.status = TaskModel.StatusChoices.COMPLETED_SUCCESS
                task.completed_at = timezone.now()
                task.is_success = True
            except Exception as e:
                logger.exception(f"{name} task failed", exc_info=e)
                if task:
                    task.status = TaskModel.StatusChoices.FAILED
                    task.completed_at = timezone.now()
                    task.is_success = False
                    task.error = str(e)
            finally:
                if task:
                    task.save(update_fields=["status", "completed_at", "is_success", "error"])
                logger.info(f"{name} task ended")
            return result

        return wrapper

    return decorator
