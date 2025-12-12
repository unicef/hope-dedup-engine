import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from api.api_const import DEDUPLICATION_SET_APPROVE_OR_REJECT, DEDUPLICATION_SET_DETAIL_VIEW, JSON
from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding
from testutils.factories.api import EncodingFactory


@pytest.mark.parametrize(
    ("action", "first_expected_state", "second_expected_state"),
    [
        pytest.param("approve", Encoding.State.APPROVED, Encoding.State.REJECTED, id="approve"),
        pytest.param("reject", Encoding.State.REJECTED, Encoding.State.APPROVED, id="reject"),
    ],
)
def test_approve_or_reject_success(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    encoding_factory: EncodingFactory,
    action: str,
    first_expected_state: Encoding.State,
    second_expected_state: Encoding.State,
) -> None:
    encoding0 = encoding_factory(deduplication_set=deduplication_set)
    encoding1 = encoding_factory(deduplication_set=deduplication_set)
    data = {
        "action": action,
        "reference_pks": [encoding0.reference_pk],
    }
    response = api_client.post(
        reverse(DEDUPLICATION_SET_APPROVE_OR_REJECT, (deduplication_set.group.reference_pk,)), data=data, format=JSON
    )
    assert response.status_code == status.HTTP_200_OK
    encoding0.refresh_from_db()
    encoding1.refresh_from_db()
    assert encoding0.state == first_expected_state
    assert encoding1.state == second_expected_state
    response = api_client.get(reverse(DEDUPLICATION_SET_DETAIL_VIEW, (deduplication_set.group.reference_pk,)))
    assert response.status_code == status.HTTP_404_NOT_FOUND
