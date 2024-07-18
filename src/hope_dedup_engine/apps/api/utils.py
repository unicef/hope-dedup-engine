import requests

from hope_dedup_engine.apps.api.models import DeduplicationSet


def start_processing(_: DeduplicationSet) -> None:
    # TODO
    pass


def delete_model_data(_: DeduplicationSet) -> None:
    # TODO
    pass


REQUEST_TIMEOUT = 5


def send_notification(deduplication_set: DeduplicationSet) -> None:
    if url := deduplication_set.notification_url:
        requests.get(url, timeout=REQUEST_TIMEOUT)
