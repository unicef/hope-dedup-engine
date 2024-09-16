from django.conf import settings

import requests
from rest_framework import status
from rest_framework.exceptions import APIException

from hope_dedup_engine.apps.api.deduplication.lock import LOCK_IS_NOT_ENABLED
from hope_dedup_engine.apps.api.models import DeduplicationSet


class AlreadyProcessingError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Deduplication set is being processed already, try again later."
    default_code = "already_processing"


def start_processing(deduplication_set: DeduplicationSet) -> None:
    from hope_dedup_engine.apps.api.deduplication.lock import DeduplicationSetLock
    from hope_dedup_engine.apps.api.deduplication.process import find_duplicates

    try:
        lock = (
            DeduplicationSetLock.for_deduplication_set(deduplication_set)
            if settings.DEDUPLICATION_SET_LOCK_ENABLED
            else LOCK_IS_NOT_ENABLED
        )
        deduplication_set.state = DeduplicationSet.State.PROCESSING
        deduplication_set.save()
        find_duplicates.delay(str(deduplication_set.pk), str(lock))
    except DeduplicationSetLock.LockNotOwnedException as e:
        raise AlreadyProcessingError from e


def delete_model_data(_: DeduplicationSet) -> None:
    # TODO
    pass


REQUEST_TIMEOUT = 5


def send_notification(deduplication_set: DeduplicationSet) -> None:
    if url := deduplication_set.notification_url:
        requests.get(url, timeout=REQUEST_TIMEOUT)
