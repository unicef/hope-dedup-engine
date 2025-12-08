from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from rest_framework.test import APIClient

from api.utils import create_api_client
from hope_dedup_engine.apps.api.models import HDEToken
from testutils.factories.api import (
    HDETokenFactory,
)
from testutils.factories.user import SystemFactory, UserFactory


@pytest.fixture
def anonymous_api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def api_client(hde_token: HDEToken) -> APIClient:
    return create_api_client(hde_token)


@pytest.fixture
def another_system_api_client(db: Any) -> APIClient:
    token = HDETokenFactory(user=UserFactory(), system=SystemFactory())
    return create_api_client(token)


@pytest.fixture
def delete_model_data(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.views.delete_model_data")


@pytest.fixture(autouse=True)
def send_notification(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")
