import traceback
from enum import IntEnum
from itertools import batched, product
from itertools import combinations_with_replacement
from typing import TYPE_CHECKING, Any, Iterable

import sentry_sdk
from celery import Task, chord, shared_task, states
from celery.utils.imports import qualname
from django.conf import settings
from django_celery_boost.task import TaskRunFromSignature

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding
from hope_dedup_engine.apps.api.models.jobs import (
    EncodeChunkJob,
    DedupeChunkJob,
    CallbackFindingsJob,
    DeduplicateDatasetJob,
    SyncDnnFilesJob,
)
from hope_dedup_engine.apps.api.utils.notification import send_notification
from hope_dedup_engine.apps.faces.managers import FileSyncManager
from hope_dedup_engine.apps.faces.services.facial import dedupe_images, encode_faces
from hope_dedup_engine.config.celery import app

if TYPE_CHECKING:
    from celery.canvas import Signature


class ChunkPurpose(IntEnum):
    ENCODE = 25
    DEDUPE = 7000


def get_chunks(filenames: Iterable[str], *, purpose: ChunkPurpose) -> list[list[str]]:
    return [list(b) for b in batched(filenames, int(purpose))]  # noqa: B911


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


@app.task(base=TaskRunFromSignature, shadow_name=shadow_name)
def encode_chunk(job_id: int, version: int) -> None:
    """Encode faces in a chunk of files."""
    encode_chunk_job: EncodeChunkJob = EncodeChunkJob.objects.select_related("deduplication_set").get(
        pk=job_id, version=version
    )
    config = DeduplicationSetConfig.from_deduplication_set(encode_chunk_job.deduplication_set)
    try:
        encode_faces(
            encode_chunk_job.deduplication_set,
            encode_chunk_job.encoding_ids,
            config.face_confidence_threshold,
            config.face_coverage_threshold,
            config.deduplicate.model_name,
            config.deduplicate.detector_backend,
            align=config.deduplicate.align,
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(encode_chunk_job.deduplication_set, e)
        raise


@app.task(base=TaskRunFromSignature)
def dedupe_chunk(job_id: int, version: int) -> None:
    """Deduplicate faces in a chunk of files."""
    dedupe_chunk_job: DedupeChunkJob = DedupeChunkJob.objects.select_related("deduplication_set").get(
        pk=job_id, version=version
    )
    config = DeduplicationSetConfig.from_deduplication_set(dedupe_chunk_job.deduplication_set)
    try:
        ignored_pairs = set(dedupe_chunk_job.deduplication_set.get_ignored_pairs())
        # we need to sort records and convert queryset to list to be able to
        # check two collections for equality
        encodings0 = list(
            dedupe_chunk_job.deduplication_set.encoding_set.filter(id__in=dedupe_chunk_job.encoding_ids0).order_by("id")
        )
        encodings1 = list(Encoding.objects.filter(id__in=dedupe_chunk_job.encoding_ids1).order_by("id"))
        return dedupe_images(
            dedupe_chunk_job.deduplication_set,
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
        finish_with_error(dedupe_chunk_job.deduplication_set, e)
        raise


@app.task(base=TaskRunFromSignature)
def callback_findings(job_id: int, version: int, _: Any) -> None:
    callback_findings_job: CallbackFindingsJob = CallbackFindingsJob.objects.select_related("deduplication_set").get(
        pk=job_id, version=version
    )
    finish_with_success(callback_findings_job.deduplication_set)


@app.task(base=TaskRunFromSignature)
def deduplicate_dataset(job_id: int, version: int, _: Any) -> dict[str, Any]:
    """Deduplicate the dataset."""
    deduplicate_dataset_job: DeduplicateDatasetJob = DeduplicateDatasetJob.objects.select_related(
        "deduplication_set"
    ).get(pk=job_id, version=version)
    try:
        chunks = get_chunks(
            deduplicate_dataset_job.deduplication_set.encodings_with_embeddings().values_list("id", flat=True),
            purpose=ChunkPurpose.DEDUPE,
        )
        approved_data_chunks = get_chunks(
            Encoding.objects.filter(
                state=Encoding.State.APPROVED,
                deduplication_set__state=DeduplicationSet.State.INACTIVE,
                deduplication_set__group=deduplicate_dataset_job.deduplication_set.group,
            ).values_list("id", flat=True),
            purpose=ChunkPurpose.DEDUPE,
        )
        # here we split all encodings in chunks. later each chunk is compared to
        # all chunks. it makes all possible pairs of encodings be compared.
        tasks = [
            DedupeChunkJob.objects.create(
                deduplication_set=deduplicate_dataset_job.deduplication_set, encoding_ids0=chunk0, encoding_ids1=chunk1
            ).s()
            for chunk0, chunk1 in combinations_with_replacement(chunks, 2)
        ]
        # here we extend chunk pairs with each chunk from the deduplication set
        # encodings compared to each chunk from all approved encodings under the
        # same deduplication set group
        tasks.extend(
            [
                DedupeChunkJob.objects.create(
                    deduplication_set=deduplicate_dataset_job.deduplication_set,
                    encoding_ids0=chunk0,
                    encoding_ids1=chunk1,
                ).s()
                for chunk0, chunk1 in product(chunks, approved_data_chunks)
            ]
        )
        chord_id = chord(tasks)(
            CallbackFindingsJob.objects.create(deduplication_set=deduplicate_dataset_job.deduplication_set).s()
        )
        return {
            "deduplication_set": str(deduplicate_dataset_job.deduplication_set),
            "chord_id": str(chord_id),
            "chunks": len(chunks) + len(approved_data_chunks),
        }
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(deduplicate_dataset_job.deduplication_set, e)
        raise


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
