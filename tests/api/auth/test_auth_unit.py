import pytest
from pytest_mock import MockerFixture
from rest_framework.request import Request
from rest_framework.views import View

from hope_dedup_engine.apps.api.auth import CanUseApi, CAN_USE_API_PERMISSION


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
