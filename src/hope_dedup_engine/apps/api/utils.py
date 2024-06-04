import requests

from hope_dedup_engine.apps.api.models import DeduplicationSet


def start_processing(_: DeduplicationSet) -> None:
    pass


def delete_model_data(_: DeduplicationSet) -> None:
    pass


def send_notification(deduplication_set: DeduplicationSet) -> None:
    if url := deduplication_set.notification_url:
        requests.get(url, timeout=5)
