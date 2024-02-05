import os
import tempfile

import pytest

from .factories import (
    APITokenFactory,
    CorridorFactory,
    FinancialServiceProviderFactory,
    PaymentInstructionFactory,
    PaymentRecordFactory,
    UserFactory,
)


def pytest_configure(config):
    os.environ["TESTING"] = "1"
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "1"
    os.environ["STATIC_ROOT"] = tempfile.gettempdir()
    os.environ["CSRF_COOKIE_SECURE"] = "0"
    os.environ["SECURE_SSL_REDIRECT"] = "0"
    os.environ["SESSION_COOKIE_HTTPONLY"] = "0"
    os.environ["SESSION_COOKIE_SECURE"] = "0"


@pytest.fixture()
def user(request, db):
    return UserFactory()


@pytest.fixture()
def logged_user(client, user):
    client.force_authenticate(user)
    return user


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()
