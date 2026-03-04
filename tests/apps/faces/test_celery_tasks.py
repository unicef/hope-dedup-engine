from unittest.mock import ANY, patch

import pytest
from celery import states

from hope_dedup_engine.apps.api.models.jobs import SyncDnnFilesJob
from hope_dedup_engine.apps.faces.celery_tasks import sync_dnn_files


@pytest.fixture
def sync_dnn_files_job(db) -> SyncDnnFilesJob:
    return SyncDnnFilesJob.objects.create()


@patch("hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager")
def test_sync_dnn_files_success(mock_fsm, settings, sync_dnn_files_job):
    """Test sync_dnn_files successfully syncs all required files."""
    settings.DNN_FILES = {"model": {"filename": "f1.dat", "sources": {"azure": "b1"}}}
    sync_dnn_files_job.force = True
    sync_dnn_files_job.save()
    mock_fsm.return_value.downloader.sync.return_value = True
    assert sync_dnn_files(sync_dnn_files_job.pk, sync_dnn_files_job.version) is True
    mock_fsm.return_value.downloader.sync.assert_called_once_with("f1.dat", "b1", force=True)


@patch("hope_dedup_engine.apps.faces.celery_tasks.sync_dnn_files.update_state")
@patch("hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager", side_effect=Exception("FSM Error"))
def test_sync_dnn_files_error(mock_fsm, mock_update_state, settings, sync_dnn_files_job):
    """Test sync_dnn_files handles exceptions and updates task state."""
    settings.DNN_FILES = {"model": {"filename": "f1.dat", "sources": {"azure": "b1"}}}
    with pytest.raises(Exception, match="FSM Error"):
        sync_dnn_files(sync_dnn_files_job.pk, sync_dnn_files_job.version)

    mock_update_state.assert_called_once_with(
        state=states.FAILURE,
        meta={"exc_message": "FSM Error", "traceback": ANY},
    )
