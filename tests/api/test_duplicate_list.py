from urllib.parse import urlencode
from datetime import timedelta

import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import FINDINGS_VIEW
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Finding

UPDATED_AFTER = "updated_after"
UPDATED_BEFORE = "updated_before"


@pytest.fixture
def deduplicated_set(deduplication_set: DeduplicationSet) -> DeduplicationSet:
    deduplication_set.state = DeduplicationSet.State.DEDUPLICATED
    deduplication_set.save(update_fields=["state"])
    return deduplication_set


def findings_url(deduplication_set_pk: str) -> str:
    return reverse(FINDINGS_VIEW, kwargs={"deduplication_set_pk": deduplication_set_pk})


def test_can_list_duplicates(api_client: APIClient, deduplicated_set: DeduplicationSet, finding: Finding) -> None:
    response = api_client.get(findings_url(deduplicated_set.pk))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data.get("results")) == 1
    assert "config" in data["results"][0]


def test_findings_only_visible_when_deduplicated(
    api_client: APIClient, deduplication_set: DeduplicationSet, finding: Finding
) -> None:
    response = api_client.get(findings_url(deduplication_set.pk))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data.get("results")) == 0


@pytest.mark.parametrize(
    ("delta_hours", "filter_param", "expected"),
    [
        (-1, UPDATED_AFTER, 1),
        (1, UPDATED_AFTER, 0),
        (1, UPDATED_BEFORE, 1),
        (-1, UPDATED_BEFORE, 0),
    ],
)
def test_filter_by_datetime(
    api_client: APIClient,
    deduplicated_set: DeduplicationSet,
    finding: Finding,
    delta_hours: int,
    filter_param: str,
    expected: int,
) -> None:
    dt = (finding.updated_at + timedelta(hours=delta_hours)).isoformat()
    url = f"{findings_url(deduplicated_set.pk)}?" + urlencode({filter_param: dt})
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json().get("results")) == expected


def test_filter_by_date_range(
    api_client: APIClient,
    deduplicated_set: DeduplicationSet,
    finding: Finding,
) -> None:
    params = {
        UPDATED_AFTER: (finding.updated_at - timedelta(hours=1)).isoformat(),
        UPDATED_BEFORE: (finding.updated_at + timedelta(hours=1)).isoformat(),
    }
    url = f"{findings_url(deduplicated_set.pk)}?" + urlencode(params)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json().get("results")) == 1


def test_invalid_datetime_returns_400(api_client: APIClient, deduplicated_set: DeduplicationSet) -> None:
    query = urlencode({UPDATED_AFTER: "invalid"})
    url = f"{findings_url(deduplicated_set.pk)}?{query}"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert UPDATED_AFTER in response.json()
