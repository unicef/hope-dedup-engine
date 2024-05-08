import os

import pytest

from .factories import UserFactory


def _setup_models():
    import django
    from django.apps import apps
    from django.conf import settings
    from django.db import connection
    from django.db.backends.utils import truncate_name
    from django.db.models import Model

    database_name = "_test_hcr"
    settings.POWER_QUERY_DB_ALIAS = "default"
    settings.DATABASES["default"]["NAME"] = database_name
    settings.DATABASES["default"]["TEST"] = {"NAME": database_name}
    settings.DATABASE_ROUTERS = ()
    del settings.DATABASES["hope_ro"]
    django.setup()

    for m in apps.get_app_config("hope").get_models():
        if m._meta.proxy:
            opts = m._meta.proxy_for_model._meta
        else:
            opts = m._meta
        if opts.app_label not in ("contenttypes", "sites"):
            db_table = ("_hope_ro__{0.app_label}_{0.model_name}".format(opts)).lower()
            m._meta.db_table = truncate_name(db_table, connection.ops.max_name_length())
            # m._meta.db_tablespace = ""
            m._meta.managed = True
            m.save = Model.save


def pytest_configure(config):
    os.environ.update(
        ADMINS="",
        ALLOWED_HOSTS="*",
        AUTHENTICATION_BACKENDS="",
        DEFAULT_FILE_STORAGE="hope_dedup_engine.apps.core.storage.DataSetStorage",
        STATIC_FILE_STORAGE="hope_dedup_engine.apps.core.storage.DataSetStorage",
        DJANGO_SETTINGS_MODULE="hope_dedup_engine.config.settings",
        CATCH_ALL_EMAIL="",
        CELERY_TASK_ALWAYS_EAGER="1",
        CSRF_COOKIE_SECURE="False",
        EMAIL_BACKEND="",
        EMAIL_HOST="",
        EMAIL_HOST_PASSWORD="",
        EMAIL_HOST_USER="",
        EMAIL_PORT="",
        EMAIL_USE_SSL="",
        EMAIL_USE_TLS="",
        MAILJET_API_KEY="",
        MAILJET_SECRET_KEY="",
        MAILJET_TEMPLATE_REPORT_READY="",
        MAILJET_TEMPLATE_ZIP_PASSWORD="",
        MEDIA_ROOT="/tmp/media",
        SECURE_HSTS_PRELOAD="False",
        SECURE_SSL_REDIRECT="False",
        SECRET_KEY="123",
        SENTRY_ENVIRONMENT="",
        SENTRY_URL="",
        SESSION_COOKIE_SECURE="False",
        SESSION_COOKIE_NAME="hcr_test",
        SESSION_COOKIE_DOMAIN="",
        STATIC_ROOT="/tmp/static",
        SIGNING_BACKEND="django.core.signing.TimestampSigner",
        WP_PRIVATE_KEY="",
    )
    if not config.option.with_sentry:
        os.environ["SENTRY_DSN"] = ""
    else:
        os.environ["SENTRY_ENVIRONMENT"] = config.option.sentry_environment

    if not config.option.enable_selenium:
        config.option.enable_selenium = "selenium" in config.option.markexpr

    # if not config.option.enable_selenium:
    #     if config.option.markexpr:
    #         config.option.markexpr = "not selenium"
    #     elif config.option.markexpr:
    #         config.option.markexpr += " and not selenium"

    config.addinivalue_line("markers", "skip_test_if_env(env): this mark skips the tests for the given env")
    _setup_models()
    from django.conf import settings

    settings.MEDIA_ROOT = "/tmp/media"
    settings.STATIC_ROOT = "/tmp/static"
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    os.makedirs(settings.STATIC_ROOT, exist_ok=True)

    from django.core.management import CommandError, call_command

    try:
        call_command("env", check=True)
    except CommandError:
        pytest.exit("FATAL: Environment variables missing")


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
