import traceback
from enum import IntEnum
from itertools import batched, product
from itertools import combinations_with_replacement
from typing import TYPE_CHECKING, Any, Iterable
from uuid import UUID

import sentry_sdk
from celery import Task, chord, shared_task, states
from celery.utils.imports import qualname
from django.conf import settings

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding
from hope_dedup_engine.apps.api.utils.notification import send_notification
from hope_dedup_engine.apps.faces.managers import FileSyncManager
from hope_dedup_engine.apps.faces.services.facial import dedupe_images, encode_faces
from hope_dedup_engine.config.celery import DedupeTask, app

if TYPE_CHECKING:
    from celery.canvas import Signature


class ChunkPurpose(IntEnum):
    ENCODE = 25
    DEDUPE = 7000


def get_chunks(filenames: Iterable[str], *, purpose: ChunkPurpose) -> list[list[str]]:
    return [list(b) for b in batched(filenames, int(purpose))]  # noqa: B911


def notify_status(task: Task, dedup_job_id: int | None = None, **kwargs):
    # This is temporary and should be replaced with proper logging or removed completely
    return True


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
    send_notification(ds)


def finish_with_error(ds: DeduplicationSet, error: Exception) -> None:
    finish_processing(ds, error)


def finish_with_success(ds: DeduplicationSet) -> None:
    finish_processing(ds)


@app.task(bind=True, base=DedupeTask, shadow_name=shadow_name)
def encode_chunk(
    self: DedupeTask,
    deduplication_set_id: UUID,
    encoding_ids: list[UUID],
) -> None:
    """Encode faces in a chunk of files."""
    deduplication_set = DeduplicationSet.objects.get(pk=deduplication_set_id)
    config = DeduplicationSetConfig.from_deduplication_set(deduplication_set)
    try:
        encode_faces(
            deduplication_set,
            encoding_ids,
            config.face_confidence_threshold,
            config.face_coverage_threshold,
            config.deduplicate.model_name,
            config.deduplicate.detector_backend,
            align=config.deduplicate.align,
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(deduplication_set, e)
        raise


@app.task(bind=True, base=DedupeTask)
def dedupe_chunk(
    self: Task,
    deduplication_set_id: UUID,
    encoding_ids0: list[UUID],
    encoding_ids1: list[UUID],
) -> None:
    """Deduplicate faces in a chunk of files."""
    ds = DeduplicationSet.objects.get(pk=deduplication_set_id)
    config = DeduplicationSetConfig.from_deduplication_set(ds)
    try:
        ignored_pairs = set(ds.get_ignored_pairs())
        # we need to sort records and convert queryset to list to be able to
        # check two collections for equality
        encodings0 = list(ds.encoding_set.filter(id__in=encoding_ids0).order_by("id"))
        encodings1 = list(Encoding.objects.filter(id__in=encoding_ids1).order_by("id"))
        return dedupe_images(
            ds,
            encodings0,
            encodings1,
            ignored_pairs,
            config.duplicate_confidence_threshold,
            config.deduplicate.model_name,
            config.deduplicate.detector_backend,
            config.deduplicate.distance_metric,
            config.deduplicate.align,
            config.deduplicate.silent,
        )
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise


@app.task(bind=True, base=DedupeTask)
def callback_findings(
    self: Task,
    deduplication_set_id: UUID,
) -> None:
    ds = DeduplicationSet.objects.get(pk=deduplication_set_id)
    finish_with_success(ds)


@app.task(bind=True, base=DedupeTask)
def deduplicate_dataset(
    self: Task,
    deduplication_set_id: UUID,
) -> dict[str, Any]:
    """Deduplicate the dataset."""
    ds = DeduplicationSet.objects.get(pk=deduplication_set_id)
    try:
        chunks = get_chunks(ds.encodings_with_embeddings().values_list("id", flat=True), purpose=ChunkPurpose.DEDUPE)
        approved_data_chunks = get_chunks(
            Encoding.objects.filter(
                state=Encoding.State.APPROVED,
                deduplication_set__state=DeduplicationSet.State.INACTIVE,
                deduplication_set__group=ds.group,
            ).values_list("id", flat=True),
            purpose=ChunkPurpose.DEDUPE,
        )
        # here we split all encodings in chunks. later each chunk is compared to
        # all chunks. it makes all possible pairs of encodings be compared.
        tasks = [
            dedupe_chunk.s(deduplication_set_id, chunk0, chunk1)
            for chunk0, chunk1 in combinations_with_replacement(chunks, 2)
        ]
        # here we extend chunk pairs with each chunk from the deduplication set
        # encodings compared to each chunk from all approved encodings under the
        # same deduplication set group
        tasks.extend(
            [
                dedupe_chunk.s(deduplication_set_id, chunk0, chunk1)
                for chunk0, chunk1 in product(chunks, approved_data_chunks)
            ]
        )
        chord_id = chord(tasks)(callback_findings.si(deduplication_set_id=deduplication_set_id))
        return {
            "deduplication_set": str(ds),
            "chord_id": str(chord_id),
            "chunks": len(chunks) + len(approved_data_chunks),
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
