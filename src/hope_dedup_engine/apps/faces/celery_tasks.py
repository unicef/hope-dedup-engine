from functools import partial
from typing import Any, Final, TYPE_CHECKING

from constance import config as constance_cfg
from django.db import connection

import sentry_sdk
from celery import Task, chord, group, shared_task, signals
from celery.utils.imports import qualname

from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet, Finding, Image
from hope_dedup_engine.apps.api.models.deduplication import Encoding
from hope_dedup_engine.apps.api.utils.notification import send_notification
from hope_dedup_engine.apps.faces.services.facial import encode_faces
from hope_dedup_engine.apps.faces.utils import is_facial_error, report_long_execution
from hope_dedup_engine.config.celery import DedupeTask, app

if TYPE_CHECKING:
    from celery.canvas import Signature


CHUNK_SIZE: Final[int] = 25


def get_chunks(files: list[str]) -> list[list[str]]:
    chunk_size = min(CHUNK_SIZE, len(files))
    if not chunk_size:
        return []
    return [files[i : i + chunk_size] for i in range(0, len(files), chunk_size)]


def notify_status(current_step: int, current_file: str, task: Task, dedup_job_id: int, **kwargs: Any) -> None:
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
    except (KeyError, AttributeError, TypeError) as e:
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
    deduplication_set_id: str,
) -> None:
    """Encode faces and save embeddings directly to the database."""
    ds = DeduplicationSet.objects.get(pk=deduplication_set_id)
    try:
        callback = partial(notify_status, task=self, dedup_job_id=ds.dedupjob.pk)
        encodings_to_update = []
        if files:
            with report_long_execution("encode_faces(...)"):
                results = encode_faces(files, config.get("encoding"), progress=callback)

            for filename, result in results.items():
                if is_facial_error(result):
                    status_code = result
                    if isinstance(result, str):
                        status_code = Image.StatusCode[result].value
                    encodings_to_update.append(
                        Encoding(
                            deduplication_set=ds,
                            filename=filename,
                            embedding=None,
                            status_code=status_code,
                        )
                    )
                else:
                    encodings_to_update.append(
                        Encoding(
                            deduplication_set=ds,
                            filename=filename,
                            embedding=result,
                            status_code=Image.StatusCode.DEDUPLICATE_SUCCESS.value,
                        )
                    )
        with report_long_execution("Encoding.objects.bulk_create"):
            if encodings_to_update:
                Encoding.objects.bulk_create(
                    encodings_to_update,
                    update_conflicts=True,
                    unique_fields=["deduplication_set", "filename"],
                    update_fields=["embedding", "status_code"],
                )
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise


@app.task(bind=True, base=DedupeTask)
def find_duplicates_in_set(
    self: Task, results: list[None], config: dict[str, Any], deduplication_set_id: str
) -> dict[str, Any]:
    """Find duplicates using pgvector, create Findings, and finalize the process."""
    ds = DeduplicationSet.objects.get(pk=deduplication_set_id)
    try:
        threshold = config.get("deduplicate", {}).get("threshold", constance_cfg.FACE_DISTANCE_THRESHOLD)
        # pgvector cosine distance is 1 - similarity. So similarity >= threshold is distance <= 1 - threshold
        distance_threshold = 1 - threshold
        findings_to_create = []

        # Get filename -> reference_pk mapping
        images = Image.objects.filter(deduplication_set=ds).values("filename", "reference_pk")
        filename_to_pk = {img["filename"]: img["reference_pk"] for img in images}

        # Create findings for images that failed to encode
        error_encodings = Encoding.objects.filter(deduplication_set=ds, embedding__isnull=True).select_related()
        findings_to_create.extend(
            [
                Finding(
                    deduplication_set=ds,
                    first_filename=enc.filename,
                    first_reference_pk=filename_to_pk.get(enc.filename),
                    second_filename="",
                    second_reference_pk="",
                    score=0,
                    status_code=enc.status_code,
                )
                for enc in error_encodings
            ]
        )

        # Find duplicates for successfully encoded images using a single raw SQL query for performance.
        query = f"""
            SELECT
                e1.filename AS first_filename,
                e2.filename AS second_filename,
                1 - (e1.embedding <=> e2.embedding) AS score
            FROM
                {Encoding._meta.db_table} e1
            JOIN
                {Encoding._meta.db_table} e2 ON e1.id < e2.id
            WHERE
                e1.deduplication_set_id = %s
                AND e2.deduplication_set_id = %s
                AND e1.embedding IS NOT NULL
                AND e2.embedding IS NOT NULL
                AND (e1.embedding <=> e2.embedding) <= %s
        """  # noqa: S608
        with connection.cursor() as cursor:
            cursor.execute(query, [ds.pk, ds.pk, distance_threshold])
            columns = [col[0] for col in cursor.description]
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row, strict=False))
                first_filename = row_dict["first_filename"]
                second_filename = row_dict["second_filename"]
                findings_to_create.append(
                    Finding(
                        deduplication_set=ds,
                        first_filename=first_filename,
                        first_reference_pk=filename_to_pk.get(first_filename),
                        second_filename=second_filename,
                        second_reference_pk=filename_to_pk.get(second_filename),
                        score=row_dict["score"],
                        status_code=Image.StatusCode.DEDUPLICATE_SUCCESS.value,
                    )
                )
        if findings_to_create:
            Finding.objects.bulk_create(findings_to_create, ignore_conflicts=True)

        finish_with_success(ds)

        return {
            "Files": ds.image_set.count(),
            "Config": config.get("deduplicate"),
            "Findings": len(findings_to_create),
        }
    except Exception as e:
        sentry_sdk.capture_exception(e)
        finish_with_error(ds, e)
        raise


@shared_task(bind=True)
def process_deduplication_set(self: Task, *args: Any, **kwargs: Any) -> None:
    """Orchestrator task to run the full deduplication process for a set."""
    # The task can be called with incorrect arguments; we fetch the correct objects via the task ID.
    dedup_job = DedupJob.objects.select_related("deduplication_set__config").get(curr_async_result_id=self.request.id)
    ds = dedup_job.deduplication_set
    deduplication_set_id = str(ds.id)
    config = ds.config.settings if ds.config and ds.config.settings else {}

    try:
        all_files = set(ds.image_set.values_list("filename", flat=True))
        if not all_files:
            finish_with_success(ds)
            return

        existing_encoded_files = set(
            Encoding.objects.filter(deduplication_set=ds, filename__in=all_files).values_list("filename", flat=True)
        )
        files_to_process = list(all_files - existing_encoded_files)

        chunks = get_chunks(files_to_process)
        # Create a group of encoding tasks
        encode_tasks = group(encode_chunk.s(chunk, config, deduplication_set_id) for chunk in chunks)

        # Create a chord that runs find_duplicates_in_set after all encoding tasks are done
        callback = find_duplicates_in_set.s(config, deduplication_set_id)

        chord(encode_tasks)(callback)

    except Exception as e:
        finish_with_error(ds, e)
        sentry_sdk.capture_exception(e)
        raise
