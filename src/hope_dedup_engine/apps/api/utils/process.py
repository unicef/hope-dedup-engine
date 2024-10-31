from rest_framework import status
from rest_framework.exceptions import APIException

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.jobs import DedupJob


class AlreadyProcessingError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Deduplication set is being processed already, try again later."
    default_code = "already_processing"


def start_processing(deduplication_set: DeduplicationSet) -> None:
    from hope_dedup_engine.apps.api.deduplication.lock import DeduplicationSetLock

    try:
        DedupJob.objects.create(deduplication_set=deduplication_set).queue()
    except DeduplicationSetLock.LockNotOwnedException as e:
        raise AlreadyProcessingError from e


def delete_model_data(_: DeduplicationSet) -> None:
    # TODO
    pass
