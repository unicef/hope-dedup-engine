import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DEDUPLICATION_SET_APPROVE_OR_REJECT, DEDUPLICATION_SET_DETAIL_VIEW, JSON
from hope_dedup_engine.apps.api.models import DeduplicationSet
from testutils.factories.api import EncodingFactory


@pytest.mark.parametrize(
    ("action", "expected_dedup_set_state"),
    [
        pytest.param("approve", DeduplicationSet.State.INACTIVE, id="approve"),
        pytest.param("reject", DeduplicationSet.State.REJECTED, id="reject"),
    ],
)
def test_approve_or_reject_success(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    encoding_factory: EncodingFactory,
    action: str,
    expected_dedup_set_state: DeduplicationSet.State,
) -> None:
    encoding_factory(deduplication_set=deduplication_set)
    encoding_factory(deduplication_set=deduplication_set)
    data = {"action": action}
    response = api_client.post(
        reverse(DEDUPLICATION_SET_APPROVE_OR_REJECT, (deduplication_set.group.reference_pk,)), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_200_OK
    deduplication_set.refresh_from_db()
    assert deduplication_set.state == expected_dedup_set_state
    response = api_client.get(reverse(DEDUPLICATION_SET_DETAIL_VIEW, (deduplication_set.group.reference_pk,)))
    assert response.status_code == status.HTTP_404_NOT_FOUND
