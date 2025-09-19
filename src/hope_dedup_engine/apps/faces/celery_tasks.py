import traceback
from functools import partial
import json
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

TARGET_CHUNKS: Final[int] = 30


def get_chunks(files: list[str]) -> list[list[str]]:
    """Divide elements into a target number of chunks for parallel processing."""
    if not files:
        return []
    num_chunks = min(len(files), TARGET_CHUNKS)
    chunk_size = (len(files) + num_chunks - 1) // num_chunks
    return [files[i : i + chunk_size] for i in range(0, len(files), chunk_size)]


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


@app.task(bind=True, base=DedupeTask, shadow_name=shadow_name, acks_late=True)
def encode_chunk(
    self: DedupeTask,
    files: list[str],
    config: dict[str, Any],
) -> list[str]:
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
        return results[1]
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise


@app.task(bind=True, base=DedupeTask, acks_late=True)
def dedupe_chunk(
    self: Task,
    chunk_path1: str,
    chunk_path2: str,
    ignored_pairs_path: str,
    config: dict[str, Any],
) -> FindingType:
    """Deduplicate faces between two chunks of files."""
    ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
    try:
        with default_storage.open(chunk_path1, "r") as f:
            encodings1 = json.load(f)

        if chunk_path1 == chunk_path2:
            encodings2 = encodings1
        else:
            with default_storage.open(chunk_path2, "r") as f:
                encodings2 = json.load(f)

        with default_storage.open(ignored_pairs_path, "r") as f:
            ignored_pairs = {tuple(p) for p in json.load(f)}

        callback = partial(notify_status, task=self, config=config)
        return dedupe_images(
            encodings1,
            encodings2,
            ignored_pairs,
            dedupe_threshold=config.get("deduplicate", {}).get("threshold"),
            options=config.get("deduplicate"),
            progress=callback,
        )
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise


@app.task(bind=True, base=DedupeTask)
def callback_findings(
    self: Task,
    results: FindingType,
    context: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate and save findings."""
    ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
    cached_data_dir = context["cached_data_dir"]
    num_new_chunks = context["num_new_chunks"]
    num_existing_chunks = context["num_existing_chunks"]
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
        try:
            ignored_pairs_path = os.path.join(cached_data_dir, "ignored_pairs.json")
            default_storage.delete(ignored_pairs_path)
            for i in range(num_new_chunks):
                chunk_path = os.path.join(cached_data_dir, f"new_chunk_{i}.json")
                default_storage.delete(chunk_path)
            for i in range(num_existing_chunks):
                chunk_path = os.path.join(cached_data_dir, f"existing_chunk_{i}.json")
                default_storage.delete(chunk_path)
        except OSError as e:
            sentry_sdk.capture_exception(e)


@app.task(bind=True, base=DedupeTask)
def callback_encodings(
    self: Task,
    results: list[list[str]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Cache encodings and ignored pairs, then start deduplication."""
    ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
    try:
        new_files = {file for file_list in results for file in file_list}
        encodings = ds.get_encodings()
        ignored_pairs = list(ds.get_ignored_pairs())  # Must be list for json

        new_encodings = {f: encodings[f] for f in new_files if f in encodings}
        existing_encodings = {f: e for f, e in encodings.items() if f not in new_files}

        # Split encodings into chunks
        new_key_chunks = get_chunks(list(new_encodings.keys()))
        existing_key_chunks = get_chunks(list(existing_encodings.keys()))
        num_new_chunks = len(new_key_chunks)
        num_existing_chunks = len(existing_key_chunks)

        cached_data_dir = f"encodings/{ds.pk}"

        # Save ignored pairs
        ignored_pairs_path = os.path.join(cached_data_dir, "ignored_pairs.json")
        payload = json.dumps(ignored_pairs)
        default_storage.save(ignored_pairs_path, ContentFile(payload.encode()))

        # Save encoding chunks
        for i, key_chunk in enumerate(new_key_chunks):
            chunk_encodings = {k: new_encodings[k] for k in key_chunk}
            chunk_path = os.path.join(cached_data_dir, f"new_chunk_{i}.json")
            payload = json.dumps(chunk_encodings)
            default_storage.save(chunk_path, ContentFile(payload.encode()))

        for i, key_chunk in enumerate(existing_key_chunks):
            chunk_encodings = {k: existing_encodings[k] for k in key_chunk}
            chunk_path = os.path.join(cached_data_dir, f"existing_chunk_{i}.json")
            payload = json.dumps(chunk_encodings)
            default_storage.save(chunk_path, ContentFile(payload.encode()))

        deduplicate_dataset.delay(
            config=config,
            cached_data_dir=cached_data_dir,
            num_new_chunks=num_new_chunks,
            num_existing_chunks=num_existing_chunks,
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
    cached_data_dir: str,
    num_new_chunks: int,
    num_existing_chunks: int,
) -> dict[str, Any]:
    """Deduplicate the dataset."""
    ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
    try:
        tasks = []
        ignored_pairs_path = os.path.join(cached_data_dir, "ignored_pairs.json")
        # new vs new
        for i in range(num_new_chunks):
            for j in range(i, num_new_chunks):
                chunk_path1 = os.path.join(cached_data_dir, f"new_chunk_{i}.json")
                chunk_path2 = os.path.join(cached_data_dir, f"new_chunk_{j}.json")
                tasks.append(dedupe_chunk.s(chunk_path1, chunk_path2, ignored_pairs_path, config))

        # new vs existing
        for i in range(num_new_chunks):
            for j in range(num_existing_chunks):
                chunk_path1 = os.path.join(cached_data_dir, f"new_chunk_{i}.json")
                chunk_path2 = os.path.join(cached_data_dir, f"existing_chunk_{j}.json")
                tasks.append(dedupe_chunk.s(chunk_path1, chunk_path2, ignored_pairs_path, config))

        context = {
            "cached_data_dir": cached_data_dir,
            "num_new_chunks": num_new_chunks,
            "num_existing_chunks": num_existing_chunks,
        }
        callback = callback_findings.s(
            config=config,
            context=context,
        )
        chord_id = chord(tasks)(callback)
        return {
            "deduplication_set": str(ds),
            "chord_id": str(chord_id),
            "tasks": len(tasks),
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
