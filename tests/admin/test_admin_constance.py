from typing import TYPE_CHECKING

import pytest
from django.test.client import RequestFactory
from django.urls import reverse
from django_webtest import DjangoTestApp
from django_webtest.pytest_plugin import MixinWithInstanceVariables
from constance.test import override_config
from django.test import override_settings

from hope_dedup_engine.utils.constance import WriteOnlyTextInput
from testutils.factories import SuperUserFactory


if TYPE_CHECKING:
    from django.http import HttpRequest


@pytest.fixture
def app(django_app_factory: MixinWithInstanceVariables, rf: RequestFactory) -> DjangoTestApp:
    django_app = django_app_factory(csrf_checks=False)
    admin_user = SuperUserFactory(username="superuser")
    django_app.set_user(admin_user)
    django_app._user = admin_user
    request: HttpRequest = rf.get("/")
    request.user = admin_user
    return django_app


def test_save_constance(app: DjangoTestApp) -> None:
    url = reverse("admin:constance_config_changelist")
    res = app.get(url)
    res = res.forms["changelist-form"].submit()
    assert res.status_code == 302


@override_settings(
    CONFIG={"HOPE_API_TOKEN": ("very-secret-token", "desc")},
    CONSTANCE_CONFIG={"HOPE_API_TOKEN": ("very-secret-token", "desc")},
    CONSTANCE_DEFAULTS_MASK="***",
)
@pytest.mark.parametrize(
    ("posted", "expected"),
    [
        ("\n   ***   \n", "very-secret-token"),
        ("new-value", "new-value"),
    ],
    ids=["mask", "new_value"],
)
def test_write_only_value_from_datadict_mask_and_value(posted: str, expected: str) -> None:
    widget = WriteOnlyTextInput()

    with override_config(HOPE_API_TOKEN="current-secret-token"):
        assert widget.value_from_datadict({"HOPE_API_TOKEN": posted}, None, "HOPE_API_TOKEN") == expected
