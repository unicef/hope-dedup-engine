from unittest.mock import MagicMock

import pytest
from hope_api_auth.models import APIToken
from pytest_mock import MockerFixture
from rest_framework.test import APIClient

from api.utils import create_api_client


@pytest.fixture
def anonymous_api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def api_client(api_token: APIToken) -> APIClient:
    return create_api_client(api_token)


@pytest.fixture
def delete_model_data(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.views.delete_model_data")


@pytest.fixture(autouse=True)
def send_notification(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
