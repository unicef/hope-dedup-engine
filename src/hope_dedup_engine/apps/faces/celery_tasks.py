import traceback

from celery import shared_task, states

from hope_dedup_engine.apps.faces.utils.celery_utils import task_lifecycle
from hope_dedup_engine.apps.faces.utils.duplication_detector import DuplicationDetector


@shared_task(bind=True, soft_time_limit=0.5 * 60 * 60, time_limit=1 * 60 * 60)
@task_lifecycle(name="Deduplicate", ttl=1 * 60 * 60)
# TODO: Use DeduplicationSet objects as input to deduplication pipeline
def deduplicate(self, filenames: tuple[str], ignore_pairs: tuple[tuple[str, str]] = tuple()) -> tuple[tuple[str]]:
    """
    Deduplicate a set of filenames, ignoring any specified pairs of filenames.

    Args:
        filenames (tuple[str]): A tuple of filenames to process.
        ignore_pairs (tuple[tuple[str, str]]): A tuple of tuples, where each inner tuple contains
                                        a pair of filenames to be ignored in the duplication check.

    Returns:
        tuple[tuple[str]]: A tuple of tuples, where each inner tuple represents a group of duplicates.
    """
    try:
        dd = DuplicationDetector(filenames, ignore_pairs)
        return dd.find_duplicates()
    except Exception as e:
        self.update_state(state=states.FAILURE, meta={"exc_message": str(e), "traceback": traceback.format_exc()})
        raise e
