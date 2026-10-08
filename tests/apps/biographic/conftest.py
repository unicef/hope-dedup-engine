from unittest.mock import MagicMock

import pytest
from hope_api_auth.models import APIToken
from rest_framework.test import APIClient

from hope_dedup_engine.apps.api.grant import Grant
from testutils.factories.auth import APITokenFactory
from testutils.factories.user import UserFactory

from api.utils import create_api_client


@pytest.fixture
def biographic_client(db) -> APIClient:
    token: APIToken = APITokenFactory(user=UserFactory(), grants=[Grant.API_BIOGRAPHIC.value])
    return create_api_client(token)


@pytest.fixture
def queued_tasks(mocker) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.biographic.services.current_app.send_task")
