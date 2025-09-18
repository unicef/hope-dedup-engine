import traceback
from functools import partial
import pickle
import os
from typing import Any, Final, TYPE_CHECKING

from django.conf import settings
from django.core.files.base import ContentFile

import sentry_sdk
from celery import Task, chord, shared_task, signals, states
from django.core.files.storage import default_storage
from celery.utils.imports import qualname

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.utils.notification import send_notification
from hope_dedup_engine.apps.faces.managers import FileSyncManager
from hope_dedup_engine.apps.faces.services.facial import dedupe_images, encode_faces
from hope_dedup_engine.apps.faces.utils import report_long_execution
from hope_dedup_engine.config.celery import DedupeTask, app
from hope_dedup_engine.type_aliases import FindingType

if TYPE_CHECKING:
    from celery.canvas import Signature

CHUNK_SIZE: Final[int] = 25


def get_chunks(files: list[str]) -> list[list[str]]:
    chunk_size = min(CHUNK_SIZE, len(files))
    if not chunk_size:
        return []
    return [
        files[i : i + chunk_size]
        for i in range(0, len(files), chunk_size)  # noqa 203
    ]


def notify_status(task: Task, config: dict[str, Any], **kwargs):
    dedup_job_id = config.get("dedup_job_id")
    signals.task_prerun.send(
        sender=task,
        task_id=task.request.id,
        dedup_job_id=dedup_job_id,
    )


def shadow_name(task, args, kwargs, options):
    try:
        s: Signature = options["chord"]
        group: str = options["group_id"].split("-")[-1]
        chunk = int(options["group_index"])
        return f"{qualname(s.type)}({group})-{chunk:03}"
    # we do not care about the actual error here
    except Exception as e:  # noqa: BLE001
        sentry_sdk.capture_exception(e)
        return str(e)


def finish_processing(ds: DeduplicationSet, error: Exception | None = None) -> None:
    if error:
        ds.set_state(DeduplicationSet.State.FAILED, error)
    else:
        ds.set_state(DeduplicationSet.State.READY)
    send_notification(ds.notification_url)


def finish_with_error(ds: DeduplicationSet, error: Exception) -> None:
    finish_processing(ds, error)


def finish_with_success(ds: DeduplicationSet) -> None:
    finish_processing(ds)


@app.task(bind=True, base=DedupeTask, shadow_name=shadow_name)
def encode_chunk(
    self: DedupeTask,
    files: list[str],
    config: dict[str, Any],
) -> None:
    """Encode faces in a chunk of files."""
    with report_long_execution('DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))'):
        ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
    try:
        callback = partial(notify_status, task=self, config=config)
        with report_long_execution("ds.get_encodings()"):
            pre_encodings = ds.get_encodings()
        with report_long_execution('encode_faces(files, config.get("encoding"), pre_encodings, progress=callback)'):
            results = encode_faces(files, config.get("encoding"), pre_encodings, progress=callback)
        with report_long_execution("ds.update_encodings(results[0])"):
            ds.update_encodings(results[0])
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise


@app.task(bind=True, base=DedupeTask)
def dedupe_chunk(
    self: Task,
    chunk: list[str],
    config: dict[str, Any],
    cached_data_path: str,
) -> FindingType:
    """Deduplicate faces in a chunk of files."""
    try:
        with default_storage.open(cached_data_path, "rb") as f:
            cached_data = pickle.load(f)

        encodings = cached_data["encodings"]
        ignored_pairs = cached_data["ignored_pairs"]

        callback = partial(notify_status, task=self, config=config)
        return dedupe_images(
            chunk,
            encodings,
            ignored_pairs,
            dedupe_threshold=config.get("deduplicate", {}).get("threshold"),
            options=config.get("deduplicate"),
            progress=callback,
        )
    except Exception as e:
        ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise


@app.task(bind=True, base=DedupeTask)
def callback_findings(
    self: Task,
    results: FindingType,
    cached_data_path: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate and save findings."""
    ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
    try:
        seen_pairs = set()
        findings = [
            record
            for d in results
            for record in d
            if (pair := tuple(sorted(record[:2]))) not in seen_pairs and not seen_pairs.add(pair)
        ]
        ds.update_findings(findings)

        finish_with_success(ds)

        return {
            "Files": len(ds.image_set.all()),
            "Config": config.get("deduplicate"),
            "Findings": len(findings),
        }
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise
    finally:
        default_storage.delete(cached_data_path)


@app.task(bind=True, base=DedupeTask)
def callback_encodings(
    self: Task,
    results: list[None],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Cache encodings and ignored pairs, then start deduplication."""
    ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
    try:
        encodings = ds.get_encodings()
        ignored_pairs = set(ds.get_ignored_pairs())
        cached_data = {"encodings": encodings, "ignored_pairs": ignored_pairs}
        cached_data_path = f"temp_encodings/{ds.pk}.pkl"
        if hasattr(default_storage, "path"):
            full_path = default_storage.path(cached_data_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with default_storage.open(cached_data_path, "wb") as f:
                pickle.dump(cached_data, f)
        else:
            default_storage.save(cached_data_path, ContentFile(pickle.dumps(cached_data)))

        deduplicate_dataset.delay(
            config=config,
            cached_data_path=cached_data_path,
        )
        return {
            "Encoded": True,
        }
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise


@app.task(bind=True, base=DedupeTask)
def deduplicate_dataset(
    self: Task,
    config: dict[str, Any],
    cached_data_path: str,
) -> dict[str, Any]:
    """Deduplicate the dataset."""
    ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
    try:
        with default_storage.open(cached_data_path, "rb") as f:
            encodings = pickle.load(f)["encodings"]

        chunks = get_chunks(list(encodings.keys()))

        tasks = [dedupe_chunk.s(chunk, config, cached_data_path) for chunk in chunks]
        callback = callback_findings.s(config=config, cached_data_path=cached_data_path)
        chord_id = chord(tasks)(callback)
        return {
            "deduplication_set": str(ds),
            "chord_id": str(chord_id),
            "chunks": len(chunks),
        }
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise


@shared_task(bind=True)
def sync_dnn_files(self: Task, force: bool = False) -> bool:
    """Synchronize DNN files from the specified source to local storage.

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
        downloader = FileSyncManager("azure").downloader
        return all(
            (
                downloader.sync(
                    info.get("filename"),
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
