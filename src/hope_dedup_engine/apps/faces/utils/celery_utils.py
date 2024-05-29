import logging
from functools import wraps

from django.conf import settings

import redis

redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)


def task_lifecycle(name: str, ttl: int):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            logger = logging.getLogger(func.__module__)
            logger.info(f"{name} task started")
            result = None

            filename: str = args[0] if args else kwargs.get("filename")
            lock_name: str = f"{name}_{filename}"
            if not _acquire_lock(lock_name, ttl):
                logger.info(f"Task {name} with brocker lock {lock_name} is already running.")
                return None

            try:
                result = func(self, *args, **kwargs)
            except Exception as e:
                logger.exception(f"{name} task failed", exc_info=e)
                raise e
            finally:
                _release_lock(lock_name)
                logger.info(f"{name} task ended")
            return result

        return wrapper

    return decorator


def _acquire_lock(lock_name: str, ttl: int = 1 * 60 * 60) -> bool:
    return redis_client.set(lock_name, "true", nx=True, ex=ttl)


def _release_lock(lock_name: str) -> None:
    redis_client.delete(lock_name)
