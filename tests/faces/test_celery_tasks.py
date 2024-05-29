from unittest.mock import patch

from celery import states
from faces_const import FILENAME, FILENAMES

from hope_dedup_engine.apps.faces.celery_tasks import deduplicate


def test_deduplicate_task_already_running(mock_redis_client, mock_duplication_detector, celery_app, celery_worker):
    mock_set, mock_delete = mock_redis_client

    mock_set.return_value = False  # Lock is not acquired
    task = deduplicate.apply(args=[FILENAME])

    assert task.result is None  # Task is not executed
    mock_duplication_detector.assert_not_called()  # DeduplicationDetector is not called
    mock_set.assert_called_once_with(f"Deduplicate_{FILENAME}", "true", nx=True, ex=3600)
    mock_delete.assert_not_called()  # Lock is not released


def test_deduplicate_task_success(dd, mock_redis_client, mock_duplication_detector, celery_app, celery_worker):
    mock_set, mock_delete = mock_redis_client
    mock_find = mock_duplication_detector
    mock_set.return_value = True  # Lock is acquired
    mock_find.return_value = set(FILENAMES[:2])  # Assuming the first two are duplicates based on mock data

    with patch("hope_dedup_engine.apps.faces.celery_tasks.DuplicationDetector", return_value=dd):
        task_result = deduplicate.apply(args=[FILENAME]).get()

    assert task_result == set(FILENAMES[:2])  # Assuming the first two are duplicates based on mock data
    mock_set.assert_called_once_with(f"Deduplicate_{FILENAME}", "true", nx=True, ex=3600)
    mock_delete.assert_called_once_with(f"Deduplicate_{FILENAME}")  # Lock is released


def test_deduplicate_task_exception_handling(
    dd, mock_redis_client, mock_duplication_detector, celery_app, celery_worker
):
    mock_set, mock_delete = mock_redis_client
    mock_find = mock_duplication_detector
    mock_find.side_effect = Exception("Simulated task failure")

    with patch("hope_dedup_engine.apps.faces.celery_tasks.DuplicationDetector", return_value=dd):
        task = deduplicate.apply(args=[FILENAME])

    assert task.state == states.FAILURE
    assert isinstance(task.result, Exception)
    assert str(task.result) == "Simulated task failure"
    assert task.traceback is not None

    mock_find.assert_called_once()
    mock_set.assert_called_once_with(f"Deduplicate_{FILENAME}", "true", nx=True, ex=3600)
    mock_delete.assert_called_once_with(f"Deduplicate_{FILENAME}")  # Lock is released
