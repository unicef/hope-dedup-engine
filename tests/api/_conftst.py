from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_factoryboy import LazyFixture, register
from pytest_mock import MockerFixture
from rest_framework.test import APIClient
from testutils.duplicate_finders import (
    AllDuplicateFinder,
    FailingDuplicateFinder,
    NoDuplicateFinder,
)
from testutils.factories.api import (
    ConfigFactory,
    DedupJobFactory,
    DeduplicationSetFactory,
    DuplicateFactory,
    IgnoredFilenamePairFactory,
    IgnoredReferencePkPairFactory,
    ImageFactory,
    TokenFactory,
)
from testutils.factories.user import ExternalSystemFactory, UserFactory

from hope_dedup_engine.apps.api.deduplication.registry import DuplicateFinder
from hope_dedup_engine.apps.api.models import DeduplicationSet, HDEToken
from hope_dedup_engine.apps.security.models import User

register(ExternalSystemFactory)
register(UserFactory)
register(DeduplicationSetFactory, system=LazyFixture("system"))
register(ImageFactory, deduplication_set=LazyFixture("deduplication_set"))
register(
    ImageFactory,
    _name="second_image",
    deduplication_Set=LazyFixture("deduplication_set"),
)
register(DuplicateFactory, deduplication_set=LazyFixture("deduplication_set"))
register(IgnoredFilenamePairFactory, deduplication_set=LazyFixture("deduplication_set"))
register(IgnoredReferencePkPairFactory, deduplication_set=LazyFixture("deduplication_set"))
register(ConfigFactory)
register(DedupJobFactory, deduplication_set=LazyFixture("deduplication_set"))


@pytest.fixture
def anonymous_api_client() -> APIClient:
    return APIClient()


def get_auth_headers(token: HDEToken) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def create_api_client(user: User) -> APIClient:
    token = TokenFactory(user=user)
    client = APIClient()
    client.credentials(**get_auth_headers(token))
    return client


@pytest.fixture
def api_client(user: User) -> APIClient:
    return create_api_client(user)


@pytest.fixture
def another_system_api_client(db: Any) -> APIClient:
    another_system_user = UserFactory()
    return create_api_client(another_system_user)


@pytest.fixture
def delete_model_data(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.views.delete_model_data")


@pytest.fixture
def start_processing(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.views.start_processing")


@pytest.fixture(autouse=True)
def send_notification(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")


@pytest.fixture
def duplicate_finders(mocker: MockerFixture) -> list[DuplicateFinder]:
    finders = []
    mock = mocker.patch("hope_dedup_engine.apps.api.deduplication.process.get_finders")
    mock.return_value = finders
    return finders


@pytest.fixture
def all_duplicates_finder(
    deduplication_set: DeduplicationSet, duplicate_finders: list[DuplicateFinder]
) -> DuplicateFinder:
    duplicate_finders.append(finder := AllDuplicateFinder(deduplication_set))
    return finder


@pytest.fixture
def no_duplicate_finder(duplicate_finders: list[DuplicateFinder]) -> DuplicateFinder:
    duplicate_finders.append(finder := NoDuplicateFinder())
    return finder


@pytest.fixture
def failing_duplicate_finder(
    duplicate_finders: list[DuplicateFinder],
) -> DuplicateFinder:
    duplicate_finders.append(finder := FailingDuplicateFinder())
    return finder
