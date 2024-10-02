from typing import Any
from unittest.mock import MagicMock

from pytest import fixture
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
register(DeduplicationSetFactory, external_system=LazyFixture("external_system"))
register(ImageFactory, deduplication_set=LazyFixture("deduplication_set"))
register(
    ImageFactory,
    _name="second_image",
    deduplication_Set=LazyFixture("deduplication_set"),
)
register(DuplicateFactory, deduplication_set=LazyFixture("deduplication_set"))
register(IgnoredFilenamePairFactory, deduplication_set=LazyFixture("deduplication_set"))
register(
    IgnoredReferencePkPairFactory, deduplication_set=LazyFixture("deduplication_set")
)
register(ConfigFactory)


@fixture
def anonymous_api_client() -> APIClient:
    return APIClient()


def get_auth_headers(token: HDEToken) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Token {token.key}"}


def create_api_client(user: User) -> APIClient:
    token = TokenFactory(user=user)
    client = APIClient()
    client.credentials(**get_auth_headers(token))
    return client


@fixture
def api_client(user: User) -> APIClient:
    return create_api_client(user)


@fixture
def another_system_api_client(db: Any) -> APIClient:
    another_system_user = UserFactory()
    return create_api_client(another_system_user)


@fixture
def delete_model_data(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.views.delete_model_data")


@fixture
def start_processing(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.views.start_processing")


@fixture(autouse=True)
def send_notification(mocker: MockerFixture) -> MagicMock:
    return mocker.patch(
        "hope_dedup_engine.apps.api.models.deduplication.send_notification"
    )


@fixture
def duplicate_finders(mocker: MockerFixture) -> list[DuplicateFinder]:
    finders = []
    mock = mocker.patch("hope_dedup_engine.apps.api.deduplication.process.get_finders")
    mock.return_value = finders
    return finders


@fixture
def all_duplicates_finder(
    deduplication_set: DeduplicationSet, duplicate_finders: list[DuplicateFinder]
) -> DuplicateFinder:
    duplicate_finders.append(finder := AllDuplicateFinder(deduplication_set))
    return finder


@fixture
def no_duplicate_finder(duplicate_finders: list[DuplicateFinder]) -> DuplicateFinder:
    duplicate_finders.append(finder := NoDuplicateFinder())
    return finder


@fixture
def failing_duplicate_finder(
    duplicate_finders: list[DuplicateFinder],
) -> DuplicateFinder:
    duplicate_finders.append(finder := FailingDuplicateFinder())
    return finder
