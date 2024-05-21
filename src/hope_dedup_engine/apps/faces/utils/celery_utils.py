import logging
from functools import wraps

from django.conf import settings
from django.utils import timezone

import redis

from hope_dedup_engine.apps.faces.models import TaskModel

redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)


def task_lifecycle(name: str, ttl: int):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            logger = logging.getLogger(func.__module__)
            logger.info(f"{name} task started")

            filename: str = args[0] if args else kwargs.get("filename")
            lock_name: str = f"{name}_{filename}"
            if not _acquire_lock(lock_name, ttl):
                logger.info(f"Task {name} with brocker lock {lock_name} is already running.")
                return None

            task: TaskModel = None
            result = None

            try:
                task = TaskModel.objects.create(name=name, celery_task_id=self.request.id)
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
                _release_lock(lock_name)
                if task:
                    task.save(update_fields=["status", "completed_at", "is_success", "error"])
                logger.info(f"{name} task ended")
            return result

        return wrapper

    return decorator


def _acquire_lock(lock_name: str, ttl: int = 1 * 60 * 60) -> bool:
    return redis_client.set(lock_name, "true", nx=True, ex=ttl)


def _release_lock(lock_name: str) -> None:
    redis_client.delete(lock_name)
