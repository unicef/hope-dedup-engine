import pytest
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

RECEIVE_INDIVIDUALS_VIEW = "receive-individuals"


@pytest.mark.django_db
def test_can_receive_valid_individuals(api_client: APIClient) -> None:
    payload = {
        "individuals": [
            {
                "reference_pk": "IND-001",
                "given_name": "John",
                "family_name": "Doe",
                "birth_date": "1990-05-15",
                "phone_no": "+1234567890",
                "identities": [{"number": "AB123456", "partner": "UNHCR"}],
            },
            {"reference_pk": "IND-002", "full_name": "Jane Smith", "sex": "FEMALE"},
        ]
    }

    response = api_client.post(reverse(RECEIVE_INDIVIDUALS_VIEW), data=payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_receive_individuals_fails_without_name(api_client: APIClient) -> None:
    payload = {"individuals": [{"reference_pk": "IND-001", "birth_date": "1990-05-15", "phone_no": "+1234567890"}]}

    response = api_client.post(reverse(RECEIVE_INDIVIDUALS_VIEW), data=payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
