import traceback
from pathlib import Path

from django.conf import settings

from celery import Task, shared_task, states
from constance import config

from hope_dedup_engine.apps.faces.services import DuplicationDetector
from hope_dedup_engine.apps.faces.utils.celery_utils import (
    download_file,
    task_lifecycle,
)


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


@shared_task(bind=True, soft_time_limit=0.1 * 60 * 60, time_limit=0.3 * 60 * 60)
def download_dnn_files(self: Task) -> bool:
    """
    Download the DNN model files for face detection if they do not already exist locally.

    Args:
        self (Task): The Celery task instance.

    Returns:
        bool: True if all files exist or are successfully downloaded, False otherwise.

    Raises:
        Exception: If any error occurs during the file download or path operations,
                   the exception is raised after updating the task state to FAILURE.
    """
    try:
        return all(
            Path(local_path).exists() or download_file(url, Path(local_path))
            for url, local_path in (
                (config.PROTOTXT_FILE_URL, settings.PROTOTXT_FILE),
                (config.CAFFEMODEL_FILE_URL, settings.CAFFEMODEL_FILE),
            )
        )
    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={"exc_message": str(e), "traceback": traceback.format_exc()},
        )
        raise e
