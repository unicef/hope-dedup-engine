from dataclasses import asdict

from celery import Task

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet, Finding
from hope_dedup_engine.apps.api.utils.notification import send_notification
from hope_dedup_engine.apps.faces.celery.pipeline import image_pipeline
from hope_dedup_engine.config.celery import app
from hope_dedup_engine.utils.celery.task_result import Result, is_error, is_value


@app.task
def clear_findings(deduplication_set_id: str) -> None:
    deduplication_set: DeduplicationSet = DeduplicationSet.objects.get(
        id=deduplication_set_id
    )

    Finding.objects.filter(deduplication_set=deduplication_set).delete()

    deduplication_set.state = DeduplicationSet.State.DIRTY
    deduplication_set.save(update_fields=["state"])
    send_notification(deduplication_set.notification_url)


@app.task
def save_pipeline_error(result: Result, deduplication_set_id: str) -> None:
    deduplication_set: DeduplicationSet = DeduplicationSet.objects.get(
        id=deduplication_set_id
    )

    if is_error(result):
        # TODO: save error in job
        pass

    if is_value(result):
        deduplication_set.state = DeduplicationSet.State.CLEAN
        deduplication_set.save(update_fields=["state"])

    send_notification(deduplication_set.notification_url)


@app.task(bind=True)
def find_duplicates(self: Task, dedup_job_id: int, version: int) -> None:
    dedup_job: DedupJob = DedupJob.objects.get(pk=dedup_job_id, version=version)
    deduplication_set = dedup_job.deduplication_set

    config = asdict(DeduplicationSetConfig.from_deduplication_set(deduplication_set))
    pipeline = (
        clear_findings.s(deduplication_set.id)
        | image_pipeline(deduplication_set, config)
        | save_pipeline_error.s(deduplication_set.id)
    )

    return self.replace(pipeline)
