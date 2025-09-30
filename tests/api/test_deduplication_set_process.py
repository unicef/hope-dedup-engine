from typing import List

import pytest
from api.api_const import DEDUPLICATION_SET_PROCESS_VIEW
from api.api_const import JSON
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.models import DeduplicationSet


def test_process_initialization_with_empty_data(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    response = api_client.post(reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,)))
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.json()


def test_process_initialization_with_empty_list(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
) -> None:
    response = api_client.post(reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,)), data=[], format=JSON)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.json()


@pytest.mark.parametrize(
    ("data", "exception_key"),
    [
        ([{"reference_pk": "12345678"}], "filename"),
        ([{"filename": "some_sick_filename"}], "reference_pk"),
    ],
)
def test_process_initialization_with_invalid_data(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
    data: List[JSON],
    exception_key: str,
):
    response = api_client.post(reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert exception_key in response.json()[0]


def test_process_initialization(
    api_client: APIClient,
    deduplication_set: DeduplicationSet,
):
    data = [
        {
            "reference_pk": "12345678",
            "filename": "filename",
        },
        {
            "reference_pk": "87654321",
            "filename": "filename2",
        },
    ]
    response = api_client.post(reverse(DEDUPLICATION_SET_PROCESS_VIEW, (deduplication_set.pk,)), data=data, format=JSON)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "started"}

    deduplication_set.refresh_from_db()
    dedup_job = deduplication_set.dedup_jobs.last()
    assert dedup_job.files_data == data
