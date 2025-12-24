from django_celery_boost.models import CeleryTaskModel
import pytest
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet
from hope_dedup_engine.apps.api.models.jobs import (
    EncodeChunkJob,
    DeduplicateDatasetJob,
    DedupeChunkJob,
    CallbackFindingsJob,
)
from hope_dedup_engine.apps.api.serializers import DeduplicationSetSerializer


def test_status_when_no_job_run(deduplication_set: DeduplicationSet) -> None:
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert serializer.get_status(deduplication_set) == CeleryTaskModel.NOT_SCHEDULED


def test_status_when_job_queued(deduplication_set: DeduplicationSet, dedup_job: DedupJob) -> None:
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert dedup_job.async_result is None
    assert serializer.get_status(deduplication_set) == CeleryTaskModel.PENDING


@pytest.mark.parametrize(
    "job_statuses",
    [
        pytest.param([CeleryTaskModel.STARTED], id="dedup job started"),
        pytest.param([CeleryTaskModel.SUCCESS, CeleryTaskModel.STARTED], id="encode chunk job started"),
        pytest.param(
            [CeleryTaskModel.SUCCESS, CeleryTaskModel.SUCCESS, CeleryTaskModel.STARTED],
            id="deduplicate dataset job started",
        ),
        pytest.param(
            [CeleryTaskModel.SUCCESS, CeleryTaskModel.SUCCESS, CeleryTaskModel.SUCCESS, CeleryTaskModel.STARTED],
            id="dedupe chunk job started",
        ),
        pytest.param(
            [
                CeleryTaskModel.SUCCESS,
                CeleryTaskModel.SUCCESS,
                CeleryTaskModel.SUCCESS,
                CeleryTaskModel.SUCCESS,
                CeleryTaskModel.STARTED,
            ],
            id="callback findings job started",
        ),
    ],
)
def test_status_when_job_started(
    mocker: MockerFixture,
    deduplication_set: DeduplicationSet,
    dedup_job: DedupJob,
    encode_chunk_job: EncodeChunkJob,
    deduplicate_dataset_job: DeduplicateDatasetJob,
    dedupe_chunk_job: DedupeChunkJob,
    callback_findings_job: CallbackFindingsJob,
    job_statuses: list[str],
) -> None:
    async_result_mock = mocker.patch("hope_dedup_engine.apps.api.models.jobs.CeleryTaskModel.async_result")
    type(async_result_mock).status = mocker.PropertyMock(side_effect=job_statuses)
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert serializer.get_status(deduplication_set) == CeleryTaskModel.STARTED


def test_status_when_job_finished(
    mocker: MockerFixture,
    deduplication_set: DeduplicationSet,
    dedup_job: DedupJob,
    encode_chunk_job: EncodeChunkJob,
    deduplicate_dataset_job: DeduplicateDatasetJob,
    dedupe_chunk_job: DedupeChunkJob,
    callback_findings_job: CallbackFindingsJob,
) -> None:
    async_result_mock = mocker.patch("hope_dedup_engine.apps.api.models.jobs.CeleryTaskModel.async_result")
    async_result_mock.status = CeleryTaskModel.SUCCESS
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert serializer.get_status(deduplication_set) == CeleryTaskModel.SUCCESS
