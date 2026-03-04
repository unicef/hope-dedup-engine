from django_celery_boost.models import CeleryTaskModel
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.models import MainJob, DeduplicationSet
from hope_dedup_engine.apps.api.serializers import DeduplicationSetSerializer


def test_status_when_no_job_run(deduplication_set: DeduplicationSet) -> None:
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert serializer.get_status(deduplication_set) == DeduplicationSetSerializer.NOT_SCHEDULED


def test_status_when_job_queued(deduplication_set: DeduplicationSet, main_job: MainJob) -> None:
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert main_job.async_result is None
    assert serializer.get_status(deduplication_set) == CeleryTaskModel.PENDING


def test_status_when_job_started(
    mocker: MockerFixture,
    deduplication_set: DeduplicationSet,
    main_job: MainJob,
) -> None:
    async_result_mock = mocker.patch("hope_dedup_engine.apps.api.models.jobs.CeleryTaskModel.async_result")
    async_result_mock.status = CeleryTaskModel.STARTED
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert serializer.get_status(deduplication_set) == CeleryTaskModel.STARTED


def test_status_when_job_finished(
    mocker: MockerFixture,
    deduplication_set: DeduplicationSet,
    main_job: MainJob,
) -> None:
    async_result_mock = mocker.patch("hope_dedup_engine.apps.api.models.jobs.CeleryTaskModel.async_result")
    async_result_mock.status = CeleryTaskModel.SUCCESS
    serializer = DeduplicationSetSerializer(deduplication_set)
    assert serializer.get_status(deduplication_set) == CeleryTaskModel.SUCCESS
