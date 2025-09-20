from unittest.mock import patch

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet
from testutils.factories.api import DedupJobFactory, DeduplicationSetFactory


@pytest.mark.django_db
def test_terminate_job_with_active_job(client):
    """Test that an active job is terminated."""
    ds = DeduplicationSetFactory()
    DedupJobFactory(deduplication_set=ds, curr_async_result_id="some-id")
    url = reverse("admin:api_deduplicationset_terminate_job", args=[ds.pk])

    mock_terminate_path = "hope_dedup_engine.apps.api.models.jobs.DedupJob.terminate"
    with patch(mock_terminate_path, return_value=DedupJob.CANCELED) as mock_terminate:
        response = client.post(url, follow=True)

    mock_terminate.assert_called_once()
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.CANCELED
    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert "Job termination initiated. New job status: CANCELED." in str(messages[0])


@pytest.mark.django_db
def test_terminate_job_with_no_job(client):
    """Test terminating when no job is associated."""
    ds = DeduplicationSetFactory()
    url = reverse("admin:api_deduplicationset_terminate_job", args=[ds.pk])

    with patch("hope_dedup_engine.apps.api.models.jobs.DedupJob.terminate") as mock_terminate:
        response = client.post(url, follow=True)

    mock_terminate.assert_not_called()
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.CANCELED
    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert "No active job found. Setting state to Canceled." in str(messages[0])


@pytest.mark.django_db
def test_terminate_job_with_job_but_no_async_id(client):
    """Test terminating when job exists but is not active (no async_result_id)."""
    ds = DeduplicationSetFactory()
    DedupJobFactory(deduplication_set=ds, curr_async_result_id=None)
    url = reverse("admin:api_deduplicationset_terminate_job", args=[ds.pk])

    with patch("hope_dedup_engine.apps.api.models.jobs.DedupJob.terminate") as mock_terminate:
        response = client.post(url, follow=True)

    mock_terminate.assert_not_called()
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.CANCELED
    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert "No active job found. Setting state to Canceled." in str(messages[0])
