import pytest
from pytest_mock import MockerFixture
from rest_framework.request import Request
from rest_framework.views import View

from hope_dedup_engine.apps.api.auth import CanUseApi, HasAccessToDeduplicationSet, CAN_USE_API_PERMISSION
from hope_dedup_engine.apps.api.models import DeduplicationSet

GROUP_REFERENCE_PK = "group_reference_pk"


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
    drf_view.kwargs.get.assert_has_calls(
        [mocker.call("deduplication_set_group__reference_pk"), mocker.call("group__reference_pk")]
    )


@pytest.mark.parametrize(
    ("deduplication_set_group_reference_pk", "group_reference_pk"),
    [
        (GROUP_REFERENCE_PK, None),
        (None, GROUP_REFERENCE_PK),
        (GROUP_REFERENCE_PK, GROUP_REFERENCE_PK),
        (None, None),
    ],
)
def test_has_access_to_deduplication_set_get_group_reference_pk(
    mocker: MockerFixture,
    drf_request: Request,
    drf_view: View,
    deduplication_set_group_reference_pk: str | None,
    group_reference_pk: str | None,
) -> None:
    drf_view.kwargs.get.side_effect = deduplication_set_group_reference_pk, group_reference_pk
    perm = HasAccessToDeduplicationSet()

    assert perm.get_group_reference_pk(drf_view) == deduplication_set_group_reference_pk or group_reference_pk

    drf_view_kwargs_get_calls = [mocker.call("deduplication_set_group__reference_pk")]
    if deduplication_set_group_reference_pk is None:
        drf_view_kwargs_get_calls.append(mocker.call("group__reference_pk"))
    drf_view.kwargs.get.assert_has_calls(drf_view_kwargs_get_calls)


def test_has_access_to_deduplication_set_get_deduplication_set(
    mocker: MockerFixture,
    drf_request: Request,
    drf_view: View,
) -> None:
    deduplication_set_model_mock = mocker.patch("hope_dedup_engine.apps.api.auth.DeduplicationSet")
    perm = HasAccessToDeduplicationSet()

    assert (
        perm.get_deduplication_set(GROUP_REFERENCE_PK)
        == deduplication_set_model_mock.objects.filter.return_value.exclude.return_value.first.return_value
    )

    deduplication_set_model_mock.assert_has_calls(
        [
            mocker.call.objects.filter(group__reference_pk=GROUP_REFERENCE_PK, group__deleted=False),
            mocker.call.objects.filter().exclude(state=deduplication_set_model_mock.State.INACTIVE),
            mocker.call.objects.filter().exclude().first(),
        ]
    )


@pytest.mark.parametrize("group_reference_pk_present", [True, False])
@pytest.mark.parametrize("deduplication_set_exists", [True, False])
@pytest.mark.parametrize("have_same_system", [True, False])
def test_has_access_to_deduplication_set_has_permission(
    mocker: MockerFixture,
    drf_request: Request,
    drf_view: View,
    group_reference_pk_present: bool,
    deduplication_set_exists: bool,
    have_same_system: bool,
) -> None:
    instance = mocker.Mock(spec=HasAccessToDeduplicationSet)
    instance.get_group_reference_pk.return_value = GROUP_REFERENCE_PK if group_reference_pk_present else None
    instance.get_deduplication_set.return_value = (
        mocker.Mock(spec=DeduplicationSet) if deduplication_set_exists else None
    )
    deduplication_set_mock = instance.get_deduplication_set.return_value
    if deduplication_set_mock:
        drf_request.auth.system = deduplication_set_mock.group.system if have_same_system else drf_request.auth.system

    has_permission = (group_reference_pk_present and deduplication_set_exists and have_same_system) or (
        not group_reference_pk_present or not deduplication_set_exists
    )

    assert HasAccessToDeduplicationSet.has_permission(instance, drf_request, drf_view) == has_permission
