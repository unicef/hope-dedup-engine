from collections.abc import Callable
from operator import attrgetter
from urllib.parse import urlencode
from datetime import timedelta

from factory.fuzzy import FuzzyText
import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from constance.test import override_config

from api.api_const import GROUP_FINDINGS_VIEW
from hope_dedup_engine.apps.api.exceptions import TooManyReferencePksException
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import Finding

REFERENCE_PK = "reference_pk"
UPDATED_AFTER = "updated_after"
UPDATED_BEFORE = "updated_before"


@pytest.fixture
def deduplicated_set(deduplication_set: DeduplicationSet) -> DeduplicationSet:
    deduplication_set.state = DeduplicationSet.State.DEDUPLICATED
    deduplication_set.save(update_fields=["state"])
    return deduplication_set


def findings_url(reference_pk: str) -> str:
    return reverse(GROUP_FINDINGS_VIEW, kwargs={"reference_pk": reference_pk})


def test_can_list_duplicates(api_client: APIClient, deduplicated_set: DeduplicationSet, finding: Finding) -> None:
    response = api_client.get(findings_url(deduplicated_set.group.reference_pk))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data.get("results")) == 1
    assert "config" in data["results"][0]


def test_findings_only_visible_when_deduplicated(
    api_client: APIClient, deduplication_set: DeduplicationSet, finding: Finding
) -> None:
    response = api_client.get(findings_url(deduplication_set.group.reference_pk))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data.get("results")) == 0


@pytest.mark.parametrize(
    ("filter_value_getter", "expected_amount"),
    [
        (attrgetter("first_encoding.reference_pk"), 1),
        (attrgetter("second_encoding.reference_pk"), 1),
        (lambda _: FuzzyText().fuzz(), 0),
    ],
)
def test_can_filter_by_reference_pk(
    api_client: APIClient,
    deduplicated_set: DeduplicationSet,
    finding: Finding,
    filter_value_getter: Callable[[Finding], str],
    expected_amount: int,
) -> None:
    url = f"{findings_url(deduplicated_set.group.reference_pk)}?" + urlencode(
        {REFERENCE_PK: filter_value_getter(finding)}
    )
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data.get("results")) == expected_amount


def test_filtering_by_multiple_reference_keys(
    api_client: APIClient, deduplicated_set: DeduplicationSet, finding_factory
) -> None:
    findings = finding_factory.create_batch(25, deduplication_set=deduplicated_set)
    reference_pks = [f.first_encoding.reference_pk for f in findings[:10]] + [
        f.second_encoding.reference_pk for f in findings[11:15]
    ]

    url = f"{findings_url(deduplicated_set.group.reference_pk)}?" + urlencode({REFERENCE_PK: ",".join(reference_pks)})
    response = api_client.get(url)
    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(data, dict)
    assert len(data.get("results")) == 14


def test_filtering_by_empty_reference_keys(api_client: APIClient, deduplicated_set: DeduplicationSet) -> None:
    url = f"{findings_url(deduplicated_set.group.reference_pk)}?" + urlencode({REFERENCE_PK: " "})
    response = api_client.get(url)
    data = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert isinstance(data, dict)
    assert not data.get("results")


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
    url = f"{findings_url(deduplicated_set.group.reference_pk)}?" + urlencode({filter_param: dt})
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
    url = f"{findings_url(deduplicated_set.group.reference_pk)}?" + urlencode(params)
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json().get("results")) == 1


def test_invalid_datetime_returns_400(api_client: APIClient, deduplicated_set: DeduplicationSet) -> None:
    query = urlencode({UPDATED_AFTER: "invalid"})
    url = f"{findings_url(deduplicated_set.group.reference_pk)}?{query}"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert UPDATED_AFTER in response.json()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("allowed_pks_count", "pks_count_in_request", "expected_status_code"),
    [
        (11, 11, status.HTTP_200_OK),
        (11, 12, status.HTTP_400_BAD_REQUEST),
    ],
)
def test_filtering_with_too_many_references(
    api_client: APIClient,
    deduplicated_set: DeduplicationSet,
    allowed_pks_count: int,
    pks_count_in_request: int,
    expected_status_code: int,
) -> None:
    reference_pks = ["1235465487981"] * pks_count_in_request
    url = f"{findings_url(deduplicated_set.group.reference_pk)}?" + urlencode({REFERENCE_PK: ",".join(reference_pks)})

    with override_config(MAX_REFERENCE_PKS_ALLOWED_FOR_FINDINGS=allowed_pks_count):
        response = api_client.get(url)
        data = response.json()

        assert response.status_code == expected_status_code

        if expected_status_code == status.HTTP_400_BAD_REQUEST:
            assert isinstance(data, dict)
            assert data.get("detail") == TooManyReferencePksException().detail
