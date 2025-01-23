import traceback

from django.conf import settings

from celery import Task, shared_task, states

from hope_dedup_engine.apps.faces.managers import FileSyncManager


@shared_task(bind=True)
def sync_dnn_files(self: Task, force: bool = False) -> bool:
    """
    A Celery task that synchronizes DNN files from the specified source to local storage.

    Args:
        self (Task): The bound Celery task instance.
        force (bool): If True, forces the re-download of files even if they already exist locally. Defaults to False.

    Returns:
        bool: True if all files were successfully synchronized, False otherwise.

    Raises:
        Exception: If any error occurs during the synchronization process. The task state is updated to FAILURE,
                   and the exception is re-raised with the associated traceback.
    """

    try:
        # downloader = FileSyncManager(config.DNN_FILES_SOURCE).downloader
        downloader = FileSyncManager("azure").downloader
        return all(
            (
                downloader.sync(
                    info.get("filename"),
                    # info.get("sources").get(config.DNN_FILES_SOURCE),
                    info.get("sources").get("azure"),
                    force=force,
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
