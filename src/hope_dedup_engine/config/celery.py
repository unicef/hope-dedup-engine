import logging
import os
from typing import Any

from django.conf import settings

import sentry_sdk
from celery import Celery, signals

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hope_dedup_engine.config.settings")

logger = logging.getLogger(__name__)

app = Celery("hpg")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@signals.celeryd_init.connect
def init_sentry(**_kwargs: Any) -> None:
    sentry_sdk.set_tag("celery", True)
