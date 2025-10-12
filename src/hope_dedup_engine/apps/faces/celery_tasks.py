import traceback
from functools import partial
import json
from typing import Any, Final, TYPE_CHECKING

from django.conf import settings
from django_redis import get_redis_connection

import sentry_sdk

from celery import Task, chord, shared_task, signals, states
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
            ds.get_encodings()
        with report_long_execution('encode_faces(files, config.get("encoding"), pre_encodings, progress=callback)'):
            results = encode_faces(files, config.get("encoding"), progress=callback)
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
    chunk_key1: str,
    chunk_key2: str,
    ignored_pairs_key: str,
    config: dict[str, Any],
) -> FindingType:
    """Deduplicate faces between two chunks of files."""
    ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
    try:
        redis_conn = get_redis_connection("default")
        encodings1 = json.loads(redis_conn.get(chunk_key1))

        if chunk_key1 == chunk_key2:
            encodings2 = encodings1
        else:
            encodings2 = json.loads(redis_conn.get(chunk_key2))

        ignored_pairs = {tuple(p) for p in json.loads(redis_conn.get(ignored_pairs_key))}

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
    keys_to_delete = context["keys_to_delete"]
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
            "Files": ds.image_set.count(),
            "Config": config.get("deduplicate"),
            "Findings": len(findings),
        }
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise
    finally:
        try:
            if keys_to_delete:
                redis_conn = get_redis_connection("default")
                redis_conn.delete(*keys_to_delete)
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
        ignored_pairs = list(ds.get_ignored_pairs())

        new_encodings = {f: encodings[f] for f in new_files if f in encodings}
        existing_encodings = {f: e for f, e in encodings.items() if f not in new_files}

        # Split encodings into chunks
        new_key_chunks = get_chunks(list(new_encodings.keys()))
        existing_key_chunks = get_chunks(list(existing_encodings.keys()))

        redis_conn = get_redis_connection("default")
        dedup_prefix = f"hde:dedup:{ds.pk}"

        # Save ignored pairs
        ignored_pairs_key = f"{dedup_prefix}:ignored_pairs"
        payload = json.dumps(ignored_pairs)
        redis_conn.set(ignored_pairs_key, payload, ex=86400)

        # Save encoding chunks
        new_chunk_keys = []
        for i, key_chunk in enumerate(new_key_chunks):
            chunk_encodings = {k: new_encodings[k] for k in key_chunk}
            key = f"{dedup_prefix}:chunk:new:{i}"
            payload = json.dumps(chunk_encodings)
            redis_conn.set(key, payload, ex=86400)
            new_chunk_keys.append(key)

        existing_chunk_keys = []
        for i, key_chunk in enumerate(existing_key_chunks):
            chunk_encodings = {k: existing_encodings[k] for k in key_chunk}
            key = f"{dedup_prefix}:chunk:existing:{i}"
            payload = json.dumps(chunk_encodings)
            redis_conn.set(key, payload, ex=86400)
            existing_chunk_keys.append(key)

        deduplicate_dataset.delay(
            config=config,
            new_chunk_keys=new_chunk_keys,
            existing_chunk_keys=existing_chunk_keys,
            ignored_pairs_key=ignored_pairs_key,
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
    new_chunk_keys: list[str],
    existing_chunk_keys: list[str],
    ignored_pairs_key: str,
) -> dict[str, Any]:
    """Deduplicate the dataset."""
    ds = DeduplicationSet.objects.get(pk=config.get("deduplication_set_id"))
    try:
        # new vs new
        tasks = [
            dedupe_chunk.s(new_chunk_keys[i], new_chunk_keys[j], ignored_pairs_key, config)
            for i in range(len(new_chunk_keys))
            for j in range(i, len(new_chunk_keys))
        ]

        # new vs existing
        tasks.extend(
            dedupe_chunk.s(chunk_key1, chunk_key2, ignored_pairs_key, config)
            for chunk_key1 in new_chunk_keys
            for chunk_key2 in existing_chunk_keys
        )

        context = {
            "keys_to_delete": new_chunk_keys + existing_chunk_keys + [ignored_pairs_key],
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
