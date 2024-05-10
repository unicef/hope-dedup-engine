from const import FILENAME, FILENAMES

from hope_dedup_engine.apps.faces.celery_tasks import deduplicate
from hope_dedup_engine.apps.faces.models import TaskModel


def test_deduplicate_task_already_running(
    mock_redis_client, mock_duplication_detector, mock_task_model, celery_app, celery_worker
):
    mock_set, mock_delete = mock_redis_client
    mock_create, _ = mock_task_model

    mock_set.return_value = False  # Lock is not acquired
    task = deduplicate.apply(args=[FILENAME])

    assert task.result is None  # Task is not executed
    mock_duplication_detector.assert_not_called()  # DeduplicationDetector is not called
    mock_set.assert_called_once_with(f"Deduplicate_{FILENAME}", "true", nx=True, ex=3600)
    mock_delete.assert_not_called()  # Lock is not released
    mock_create.assert_not_called()  # TaskModel is not created


def test_deduplicate_task_success(
    mock_redis_client, mock_duplication_detector, mock_task_model, celery_app, celery_worker
):
    mock_set, mock_delete = mock_redis_client
    mock_create, mock_task_instance = mock_task_model
    mock_find = mock_duplication_detector

    mock_set.return_value = True  # Lock is acquired
    mock_find.return_value = set(FILENAMES[:2])  # Assuming the first two are duplicates based on mock data

    task_result = deduplicate.apply(args=[FILENAME]).get()

    assert task_result == set(FILENAMES[:2])  # Assuming the first two are duplicates based on mock data
    mock_set.assert_called_once_with(f"Deduplicate_{FILENAME}", "true", nx=True, ex=3600)
    mock_delete.assert_called_once_with(f"Deduplicate_{FILENAME}")  # Lock is released

    mock_create.assert_called_once()  # TaskModel is created
    mock_task_instance.save.assert_called_once()  # TaskModel is saved
    assert mock_task_instance.status == TaskModel.StatusChoices.COMPLETED_SUCCESS
    assert mock_task_instance.is_success is True
    assert mock_task_instance.completed_at is not None


def test_deduplicate_task_exception_handling(
    mock_redis_client, mock_task_model, mock_duplication_detector, celery_app, celery_worker
):
    mock_set, mock_delete = mock_redis_client
    mock_create, mock_task_instance = mock_task_model
    mock_find = mock_duplication_detector
    mock_find.side_effect = Exception("Simulated task failure")

    task = deduplicate.apply(args=[FILENAME])

    assert task.result is None  # Task is not executed
    mock_duplication_detector.assert_called_once()  # DeduplicationDetector is called

    mock_create.assert_called_once_with(name="Deduplicate", celery_task_id=task.id)
    mock_task_instance.save.assert_called_once()
    assert mock_task_instance.status == TaskModel.StatusChoices.FAILED
    assert not mock_task_instance.is_success
    assert mock_task_instance.error == "Simulated task failure"

    # Check that the Redis lock was acquired and then released
    mock_set.assert_called_once_with(f"Deduplicate_{FILENAME}", "true", nx=True, ex=3600)
    mock_delete.assert_called_once_with(f"Deduplicate_{FILENAME}")
