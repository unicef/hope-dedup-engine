from uuid import uuid4, UUID

import pytest
from pytest_mock import MockerFixture
from rest_framework.request import Request
from rest_framework.views import View

from hope_dedup_engine.apps.api.auth import CanUseApi, HasAccessToDeduplicationSet, CAN_USE_API_PERMISSION


PK = uuid4()


@pytest.fixture
def drf_request(mocker: MockerFixture) -> Request:
    return mocker.Mock()


@pytest.fixture
def drf_view(mocker: MockerFixture) -> View:
    return mocker.Mock()


@pytest.mark.parametrize("can_use_api_perm", [True, False])
def test_can_use_api(drf_request: Request, drf_view: View, can_use_api_perm) -> None:
    perm = CanUseApi()
    drf_request.user.has_perm.return_value = can_use_api_perm

    assert perm.has_permission(drf_request, drf_view) == can_use_api_perm
    drf_request.user.has_perm.assert_called_once_with(CAN_USE_API_PERMISSION)


def test_has_access_to_deduplication_set_no_pk(mocker: MockerFixture, drf_request: Request, drf_view: View) -> None:
    drf_view.kwargs.get.return_value = None
    perm = HasAccessToDeduplicationSet()

    assert perm.has_permission(drf_request, drf_view) is True
    drf_view.kwargs.get.assert_has_calls([mocker.call("deduplication_set_pk"), mocker.call("pk")])


@pytest.mark.parametrize(
    ("deduplication_set_pk", "pk"),
    [
        (PK, None),
        (None, PK),
        (PK, PK),
    ],
)
@pytest.mark.parametrize("deduplication_set_exists", [True, False])
def test_has_access_to_deduplication_set(
    mocker: MockerFixture,
    drf_request: Request,
    drf_view: View,
    deduplication_set_pk: UUID | None,
    pk: UUID | None,
    deduplication_set_exists: bool,
) -> None:
    drf_view.kwargs.get.side_effect = deduplication_set_pk, pk
    deduplication_set_model_mock = mocker.patch("hope_dedup_engine.apps.api.auth.DeduplicationSet")
    deduplication_set_model_mock.objects.filter.return_value.exists.return_value = deduplication_set_exists
    perm = HasAccessToDeduplicationSet()

    assert perm.has_permission(drf_request, drf_view) == deduplication_set_exists
    drf_view_kwargs_get_calls = [mocker.call("deduplication_set_pk")]
    if deduplication_set_pk is None:
        drf_view_kwargs_get_calls.append(mocker.call("pk"))
    drf_view.kwargs.get.assert_has_calls(drf_view_kwargs_get_calls)
    deduplication_set_model_mock.objects.filter.assert_called_once_with(
        system=drf_request.auth.system, pk=deduplication_set_pk or pk
    )
