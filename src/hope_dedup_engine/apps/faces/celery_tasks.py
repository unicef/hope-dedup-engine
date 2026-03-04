import traceback

from celery import Task, shared_task, states
from django.conf import settings

from hope_dedup_engine.apps.api.models.jobs import SyncDnnFilesJob
from hope_dedup_engine.apps.faces.managers import FileSyncManager


@shared_task(bind=True)
def sync_dnn_files(self: Task, job_id: int, version: int) -> bool:
    """Synchronize DNN files from the specified source to local storage.

    Args:
        self (Task): The bound Celery task instance.
        job_id (int): The ID of the DeduplicationSetJob object.
        version (int): The version of the DeduplicationSetJob object.

    Returns:
        bool: True if all files were successfully synchronized, False otherwise.

    Raises:
        Exception: If any error occurs during the synchronization process. The task state is updated to FAILURE,
                   and the exception is re-raised with the associated traceback.

    """
    sync_dnn_files_job: SyncDnnFilesJob = SyncDnnFilesJob.objects.get(pk=job_id, version=version)
    try:
        downloader = FileSyncManager("azure").downloader
        return all(
            (
                downloader.sync(
                    info.get("filename"),
                    info.get("sources").get("azure"),
                    force=sync_dnn_files_job.force,
                )
            )
            for _, info in settings.DNN_FILES.items()
        )
    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={"exc_message": str(e), "traceback": traceback.format_exc()},
        )
        raise e
