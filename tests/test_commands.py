import os
from io import StringIO
from unittest import mock

from django.core.management import call_command

import pytest
from testutils.factories import SuperUserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture()
def environment():
    return {
        "ADMIN_EMAIL": "",
        "CACHE_URL": "test",
        "CELERY_BROKER_URL": "",
        "DATABASE_URL": "",
        "SECRET_KEY": "",
        "DEFAULT_ROOT": "/tmp/default",
        "MEDIA_ROOT": "/tmp/media",
        "STATIC_ROOT": "/tmp/static",
        "SECURE_SSL_REDIRECT": "1",
        "SESSION_COOKIE_SECURE": "1",
        "DJANGO_SETTINGS_MODULE": "hope_dedup_engine.config.settings",
    }


@pytest.fixture
def mock_settings():
    with mock.patch("django.conf.settings") as mock_settings:
        mock_settings.AZURE_CONTAINER_HOPE = "hope-container"
        mock_settings.AZURE_CONTAINER_DNN = "dnn-container"
        mock_settings.AZURE_CONTAINER_HDE = "hde-container"
        yield mock_settings


@pytest.mark.parametrize(
    "static_root", ["static", ""], ids=["static_missing", "static_existing"]
)
@pytest.mark.parametrize("static", [True, False], ids=["static", "no-static"])
@pytest.mark.parametrize("verbosity", [1, 0], ids=["verbose", ""])
@pytest.mark.parametrize("migrate", [True, False], ids=["migrate", ""])
def test_upgrade_init(
    verbosity, migrate, monkeypatch, environment, static, static_root, tmp_path
):
    static_root_path = tmp_path / static_root
    out = StringIO()
    with mock.patch.dict(
        os.environ,
        {**environment, "STATIC_ROOT": str(static_root_path.absolute())},
        clear=True,
    ):
        call_command(
            "upgrade",
            static=static,
            admin_email="user@test.com",
            admin_password="123",
            migrate=migrate,
            stdout=out,
            check=False,
            dnn_setup=False,
            verbosity=verbosity,
        )
    assert "error" not in str(out.getvalue())


@pytest.mark.parametrize("verbosity", [1, 0], ids=["verbose", ""])
@pytest.mark.parametrize("migrate", [1, 0], ids=["migrate", ""])
def test_upgrade(verbosity, migrate, monkeypatch, environment):
    from testutils.factories import SuperUserFactory

    out = StringIO()
    SuperUserFactory()
    with mock.patch.dict(os.environ, environment, clear=True):
        call_command(
            "upgrade",
            stdout=out,
            check=False,
            dnn_setup=False,
            verbosity=verbosity,
        )
    assert "error" not in str(out.getvalue())


# def test_upgrade_check(mocked_responses, admin_user, environment):
#     out = StringIO()
#     with mock.patch.dict(os.environ, environment, clear=True):
#         call_command("upgrade", stdout=out, check=True)


def test_upgrade_noadmin(db, mocked_responses, environment):
    out = StringIO()
    with mock.patch.dict(os.environ, environment, clear=True):
        with pytest.raises(SystemExit):
            call_command("upgrade", stdout=out, check=True, admin_email="")


@pytest.mark.parametrize("admin", [True, False], ids=["existing_admin", "new_admin"])
def test_upgrade_admin(db, mocked_responses, environment, admin):
    if admin:
        email = SuperUserFactory().email
    else:
        email = "new-@example.com"

    out = StringIO()
    with mock.patch.dict(os.environ, environment, clear=True):
        call_command(
            "upgrade",
            stdout=out,
            check=False,
            dnn_setup=False,
            static=False,
            admin_email=email,
        )


def test_upgrade_exception(mocked_responses, environment):
    with mock.patch(
        "hope_dedup_engine.apps.core.management.commands.upgrade.call_command"
    ) as m:
        m.side_effect = Exception
        with pytest.raises(SystemExit):
            call_command("upgrade")

    out = StringIO()
    with mock.patch.dict(
        os.environ,
        {"ADMIN_EMAIL": "2222", "ADMIN_USER": "admin", **environment},
        clear=True,
    ):
        with pytest.raises(SystemExit):
            call_command("upgrade", stdout=out, check=True, admin_email="")
