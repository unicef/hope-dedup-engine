from unittest.mock import PropertyMock

import pytest

from hope_dedup_engine.apps.api.models.jobs import GracefulJobCancellationError

pytestmark = pytest.mark.django_db


def test_ensure_not_cancelled_raises_when_termination_requested(main_job_factory, mocker):
    job = main_job_factory()
    mocker.patch.object(type(job), "is_termination_requested", new_callable=PropertyMock, return_value=True)
    cancel_mock = mocker.patch.object(job, "cancel")

    with pytest.raises(GracefulJobCancellationError, match=f"Cancellation requested for job #{job.pk}"):
        job.ensure_not_cancelled()

    cancel_mock.assert_not_called()


def test_ensure_not_cancelled_noop_when_not_requested(main_job_factory, mocker):
    job = main_job_factory()
    mocker.patch.object(type(job), "is_termination_requested", new_callable=PropertyMock, return_value=False)
    cancel_mock = mocker.patch.object(job, "cancel")

    job.ensure_not_cancelled()

    cancel_mock.assert_not_called()
