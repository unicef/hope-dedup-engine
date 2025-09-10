import os
from typing import Any

import sentry_sdk
from celery import Celery, Task, signals
from celery.signals import task_prerun, task_postrun
from django.db import connection

from hope_dedup_engine.config import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hope_dedup_engine.config.settings")


app = Celery("hde")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS, related_name="celery_tasks")


@task_prerun.connect
def before_task(**_: Any) -> None:
    connection.close_if_unusable_or_obsolete()


@task_postrun.connect
def after_task(**_: Any) -> None:
    connection.close()


@signals.celeryd_init.connect
def init_sentry(**_kwargs: Any) -> None:
    sentry_sdk.set_tag("celery", True)


class DedupeTask(Task):
    pass
