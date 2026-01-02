from celery import shared_task

from hope_dedup_engine.apps.api.deduplication.process import (  # noqa: F401
    find_duplicates,
)


@shared_task
def not_a_task() -> None:
    pass
