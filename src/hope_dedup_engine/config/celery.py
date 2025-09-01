import os
from typing import Any

import sentry_sdk
from celery import Celery, Task, signals

from hope_dedup_engine.config import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hope_dedup_engine.config.settings")


app = Celery("hde")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS, related_name="celery_tasks")


@signals.celeryd_init.connect
def init_sentry(**_kwargs: Any) -> None:
    sentry_sdk.set_tag("celery", True)


@signals.worker_init.connect
def reset_db_connection_pool(**_kwargs: Any) -> None:
    from django.db import connections  # noqa: PLC0415

    connections.close_all()


@signals.task_postrun.connect
def on_task_postrun(**_kwargs: Any) -> None:
    from django.db import connections  # noqa: PLC0415

    connections.close_all()


class DedupeTask(Task):
    pass
