from const import DEDUPLICATION_SET_LIST_VIEW
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.public_api.serializers import DeduplicationSetSerializer
from testutils.factories.api import DeduplicationSetFactory


def test_new_deduplication_set_status_is_clean(api_client: APIClient) -> None:
    data = DeduplicationSetSerializer(DeduplicationSetFactory.build()).data

    response = api_client.post(reverse(DEDUPLICATION_SET_LIST_VIEW), data=data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    deduplication_set = response.json()
    assert deduplication_set["state"] == DeduplicationSet.Status.CLEAN.label
