from django_celery_boost.models import CeleryTaskModel
import pytest
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.models import MainJob, DeduplicationSet
from hope_dedup_engine.apps.api.models.jobs import (
    EncodeChunkJob,
    DeduplicateDatasetJob,
    DedupeChunkJob,
    CallbackFindingsJob,
)
from hope_dedup_engine.apps.api.serializers import DeduplicationSetSerializer


def test_status_when_no_job_run(deduplication_set: DeduplicationSet) -> None:
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert serializer.get_status(deduplication_set) == DeduplicationSetSerializer.NOT_SCHEDULED


def test_status_when_job_queued(deduplication_set: DeduplicationSet, main_job: MainJob) -> None:
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert main_job.async_result is None
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
    main_job: MainJob,
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


@pytest.mark.parametrize(
    "finished_tasks",
    [
        pytest.param(1, id="encode chunk job not started"),
        pytest.param(2, id="deduplicate dataset job not started"),
        pytest.param(3, id="dedupe chunk job not started"),
        pytest.param(4, id="callback findings job not started"),
    ],
)
def test_status_when_job_started_but_task_is_not(
    mocker: MockerFixture,
    deduplication_set: DeduplicationSet,
    main_job: MainJob,
    encode_chunk_job: EncodeChunkJob,
    deduplicate_dataset_job: DeduplicateDatasetJob,
    dedupe_chunk_job: DedupeChunkJob,
    callback_findings_job: CallbackFindingsJob,
    finished_tasks: int,
) -> None:
    successful_status_mock = mocker.Mock()
    successful_status_mock.status = CeleryTaskModel.SUCCESS
    async_result_values = [successful_status_mock] * finished_tasks + [None]
    mocker.patch(
        "hope_dedup_engine.apps.api.models.jobs.CeleryTaskModel.async_result",
        new_callable=mocker.PropertyMock,
        side_effect=async_result_values,
    )
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert serializer.get_status(deduplication_set) == CeleryTaskModel.STARTED


def test_status_when_job_finished(
    mocker: MockerFixture,
    deduplication_set: DeduplicationSet,
    main_job: MainJob,
    encode_chunk_job: EncodeChunkJob,
    deduplicate_dataset_job: DeduplicateDatasetJob,
    dedupe_chunk_job: DedupeChunkJob,
    callback_findings_job: CallbackFindingsJob,
) -> None:
    async_result_mock = mocker.patch("hope_dedup_engine.apps.api.models.jobs.CeleryTaskModel.async_result")
    async_result_mock.status = CeleryTaskModel.SUCCESS
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert serializer.get_status(deduplication_set) == CeleryTaskModel.SUCCESS
