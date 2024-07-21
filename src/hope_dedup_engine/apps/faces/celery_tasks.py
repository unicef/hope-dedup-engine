import traceback
from pathlib import Path

from django.conf import settings

from celery import Task, shared_task, states
from constance import config

from hope_dedup_engine.apps.faces.managers import FileSyncManager
from hope_dedup_engine.apps.faces.services import DuplicationDetector
from hope_dedup_engine.apps.faces.utils.celery_utils import task_lifecycle


@shared_task(bind=True, soft_time_limit=0.5 * 60 * 60, time_limit=1 * 60 * 60)
@task_lifecycle(name="Deduplicate", ttl=1 * 60 * 60)
# TODO: Use DeduplicationSet objects as input to deduplication pipeline
def deduplicate(
    self: Task,
    filenames: tuple[str],
    ignore_pairs: tuple[tuple[str, str], ...] = tuple(),
) -> list[list[str]]:
    """
    Deduplicate a set of filenames, ignoring any specified pairs of filenames.

    Args:
        filenames (tuple[str]): A tuple of filenames to process.
        ignore_pairs (tuple[tuple[str, str]]): A tuple of tuples, where each inner tuple contains
                                        a pair of filenames to be ignored in the duplication check.

    Returns:
        list[list[str]]: A list of lists, where each inner list represents a group of duplicates.
    """
    try:
        dd = DuplicationDetector(filenames, ignore_pairs)
        return dd.find_duplicates()
    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={"exc_message": str(e), "traceback": traceback.format_exc()},
        )
        raise e


@shared_task(bind=True)
def sync_dnn_files(self: Task) -> bool:
    """
    Synchronizes DNN model files from the specified source to the local file system. It
    downloads the files if they do not exist locally.

    Args:
        self (Task): The Celery task instance.

    Returns:
        bool: True if all files are present and correctly synchronized, False otherwise.

    Raises:
        Exception: If any error occurs during the file synchronization,
                   the exception is raised after updating the task state to FAILURE.
    """
    try:
        downloader = FileSyncManager(config.DNN_FILES_SOURCE).downloader
        return all(
            Path(info["local_path"]).exists()
            or downloader.sync(
                info.get("sources").get(config.DNN_FILES_SOURCE),
                Path(info.get("local_path")),
            )
            for _, info in settings.DNN_FILES.items()
        )
    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={"exc_message": str(e), "traceback": traceback.format_exc()},
        )
        raise e
