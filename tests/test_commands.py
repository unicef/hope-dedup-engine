import os
from io import StringIO
from unittest import mock

from django.core.management import call_command

import pytest
from pytest_mock import MockerFixture

from testutils.factories import SuperUserFactory, UserFactory
from hope_dedup_engine.apps.core.management.commands import upgrade as upgrade_cmd

pytestmark = pytest.mark.django_db


@pytest.fixture
def environment():
    return {
        "ADMIN_EMAIL": "",
        "ADMIN_PASSWORD": "",
        "ALLOWED_HOSTS": "",
        "CACHE_URL": "test",
        "CSRF_COOKIE_SECURE": "1",
        "CELERY_BROKER_URL": "",
        "DATABASE_URL": "",
        "SECRET_KEY": "",
        "DEFAULT_ROOT": "/tmp/default",
        "MEDIA_ROOT": "/tmp/media",
        "STATIC_ROOT": "/tmp/static",
        "SECURE_SSL_REDIRECT": "1",
        "SESSION_COOKIE_SECURE": "1",
        "DJANGO_SETTINGS_MODULE": "hope_dedup_engine.config.settings",
        "DEEPFACE_HOME": "/tmp/deepface",
    }


@pytest.fixture
def mock_settings():
    with mock.patch("django.conf.settings") as mock_settings:
        mock_settings.AZURE_CONTAINER_HOPE = "hope-container"
        mock_settings.AZURE_CONTAINER_HDE = "hde-container"
        yield mock_settings


@pytest.mark.parametrize("static_root", ["static", ""], ids=["static_missing", "static_existing"])
@pytest.mark.parametrize("static", [True, False], ids=["static", "no-static"])
@pytest.mark.parametrize("verbosity", [1, 0], ids=["verbose", ""])
@pytest.mark.parametrize("migrate", [True, False], ids=["migrate", ""])
def test_upgrade_init(verbosity, migrate, monkeypatch, environment, static, static_root, tmp_path):
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
            sync_models=False,
            verbosity=verbosity,
        )
    assert "error" not in str(out.getvalue())


@pytest.mark.parametrize("verbosity", [1, 0], ids=["verbose", ""])
@pytest.mark.parametrize("migrate", [1, 0], ids=["migrate", ""])
def test_upgrade(verbosity, migrate, monkeypatch, environment):
    out = StringIO()
    SuperUserFactory()
    with mock.patch.dict(os.environ, environment, clear=True):
        call_command(
            "upgrade",
            stdout=out,
            check=False,
            sync_models=False,
            verbosity=verbosity,
        )
    assert "error" not in str(out.getvalue())


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
            sync_models=False,
            static=False,
            admin_email=email,
        )


def test_upgrade_exception(mocked_responses, environment):
    with (
        mock.patch.dict(
            os.environ,
            {"ADMIN_EMAIL": "2222", "ADMIN_USER": "admin", **environment},
            clear=True,
        ),
        mock.patch("hope_dedup_engine.apps.core.management.commands.upgrade.call_command") as m,
    ):
        m.side_effect = Exception
        with pytest.raises(SystemExit):
            call_command("upgrade")

        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("upgrade", stdout=out, check=True, admin_email="")


@pytest.mark.parametrize(
    ("factory_key", "kwargs", "expect_changed"),
    [
        ("user", {"is_staff": False, "is_superuser": False}, True),
        ("superuser", {}, False),
    ],
    ids=["promotes", "noop"],
)
def test_upgrade_ensure_superuser(
    mocker: MockerFixture,
    factory_key: str,
    kwargs: dict[str, object],
    expect_changed: bool,
) -> None:
    factory = {"user": UserFactory, "superuser": SuperUserFactory}[factory_key]
    user = factory(**kwargs)
    save_spy = mocker.spy(user, "save")

    assert upgrade_cmd.Command()._ensure_superuser(user) is expect_changed

    if expect_changed:
        assert user.is_staff is True
        assert user.is_superuser is True
        save_spy.assert_called_once_with(update_fields=["is_staff", "is_superuser"])
    else:
        save_spy.assert_not_called()


def test_upgrade_run_createsuperuser_pops_password_env_when_missing(mocker: MockerFixture) -> None:
    cmd = upgrade_cmd.Command()
    cmd.admin_email = "admin@example.com"
    cmd.admin_password = ""
    cmd.verbosity = 1

    call = mocker.patch.object(upgrade_cmd, "call_command")
    mocker.patch.dict(os.environ, {"DJANGO_SUPERUSER_PASSWORD": "stale"}, clear=True)

    assert cmd._run_createsuperuser("admin@example.com", "admin@example.com") is False
    assert "DJANGO_SUPERUSER_PASSWORD" not in os.environ

    call.assert_called_once_with(
        "createsuperuser",
        email="admin@example.com",
        username="admin@example.com",
        verbosity=0,
        interactive=False,
    )


def test_upgrade_superuser_logins_drops_whitespace_only() -> None:
    cmd = upgrade_cmd.Command()
    cmd.admin_email = " admin@example.com "
    cmd.superusers = ["  ", "u1", " u1 ", "", "   "]
    assert cmd._superuser_logins() == ["admin@example.com", "u1"]
