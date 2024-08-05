from datetime import timedelta
from unittest.mock import ANY, patch

import pytest
from celery import states
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
from constance import settings, test
from faces_const import (
    CELERY_TASK_DELAYS,
    CELERY_TASK_NAME,
    CELERY_TASK_TTL,
    FILENAMES,
    IGNORE_PAIRS,
)

from hope_dedup_engine.apps.faces.celery_tasks import deduplicate, sync_dnn_files
from hope_dedup_engine.apps.faces.utils.celery_utils import _get_hash


@pytest.mark.parametrize("lock_is_acquired", [True, False])
def test_deduplicate_task_locking(
    mock_redis_client, mock_dd_find, mock_dd, lock_is_acquired
):
    mock_set, mock_delete = mock_redis_client
    mock_set.return_value = lock_is_acquired
    mock_find = mock_dd_find

    with patch(
        "hope_dedup_engine.apps.faces.celery_tasks.DuplicationDetector",
        return_value=mock_dd,
    ):
        task_result = deduplicate.apply(args=(FILENAMES, IGNORE_PAIRS)).get()
    hash_value = _get_hash(FILENAMES, IGNORE_PAIRS)

    mock_set.assert_called_once_with(
        f"{CELERY_TASK_NAME}_{hash_value}", "true", nx=True, ex=CELERY_TASK_TTL
    )
    if lock_is_acquired:
        assert task_result == mock_find.return_value
        mock_find.assert_called_once()
        mock_delete.assert_called_once_with(f"{CELERY_TASK_NAME}_{hash_value}")
    else:
        assert task_result is None
        mock_find.assert_not_called()
        mock_delete.assert_not_called()


@pytest.mark.parametrize(
    "delay, exception",
    [
        (CELERY_TASK_DELAYS["SoftTimeLimitExceeded"], SoftTimeLimitExceeded()),
        (CELERY_TASK_DELAYS["TimeLimitExceeded"], TimeLimitExceeded()),
        (
            CELERY_TASK_DELAYS["CustomException"],
            Exception("Simulated custom task failure"),
        ),
    ],
)
def test_deduplicate_task_exception_handling(
    mock_redis_client, mock_dd_find, time_control, mock_dd, delay, exception
):
    mock_set, mock_delete = mock_redis_client
    mock_find = mock_dd_find
    mock_find.side_effect = exception

    time_control.tick(delta=timedelta(seconds=delay))

    with (
        pytest.raises(type(exception)) as exc_info,
        patch(
            "hope_dedup_engine.apps.faces.celery_tasks.DuplicationDetector",
            return_value=mock_dd,
        ),
    ):
        task = deduplicate.apply(args=(FILENAMES, IGNORE_PAIRS))
        assert exc_info.value == exception
        assert isinstance(task.result, exception)
        assert task.state == states.FAILURE
        assert str(task.result) == str(exception)
        assert task.traceback is not None

    hash_value = _get_hash(FILENAMES, IGNORE_PAIRS)
    mock_set.assert_called_once_with(
        f"{CELERY_TASK_NAME}_{hash_value}", "true", nx=True, ex=3600
    )
    mock_delete.assert_called_once_with(
        f"{CELERY_TASK_NAME}_{hash_value}"
    )  # Lock is released
    mock_find.assert_called_once()


@pytest.mark.parametrize(
    "force, file_exists, expected_call_count, result",
    [
        (False, False, 2, True),
        (False, True, 0, False),
        (True, False, 2, True),
        (True, True, 2, True),
    ],
)
def test_sync_dnn_files_success(
    mock_file_sync_manager, force, file_exists, expected_call_count, result
):
    mock_file_sync_manager.downloader.sync.return_value = True
    sources = [
        ch[0]
        for ch in settings.ADDITIONAL_FIELDS.get("dnn_files_source")[1].get("choices")
    ]
    for choice in sources:
        with test.pytest.override_config(DNN_FILES_SOURCE=choice):
            with patch(
                "hope_dedup_engine.apps.faces.celery_tasks.Path.exists",
                return_value=file_exists,
            ):
                is_downloaded = sync_dnn_files(force=force)

    assert is_downloaded is result
    assert (
        mock_file_sync_manager.downloader.sync.call_count
        == expected_call_count * len(sources)
    )


def test_sync_dnn_files_exception_handling(mock_file_sync_manager):
    mock_file_sync_manager.downloader.sync.side_effect = Exception("Download error")
    with (
        patch(
            "hope_dedup_engine.apps.faces.celery_tasks.sync_dnn_files.update_state"
        ) as mock_update_state,
        pytest.raises(Exception),
    ):
        sync_dnn_files()
        mock_update_state.assert_called_once_with(
            state=states.FAILURE,
            meta={"exc_message": "Download error", "traceback": ANY},
        )
