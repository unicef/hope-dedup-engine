import os
import sys
from pathlib import Path

import django

import pytest
import responses
from constance import config

here = Path(__file__).parent
sys.path.insert(0, str(here / "../src"))
sys.path.insert(0, str(here / "extras"))


def pytest_configure(config):
    os.environ.update(DJANGO_SETTINGS_MODULE="hope_dedup_engine.config.settings")
    os.environ.setdefault("MEDIA_ROOT", "/tmp/static/")
    os.environ.setdefault("STATIC_ROOT", "/tmp/media/")
    os.environ.setdefault("TEST_EMAIL_SENDER", "sender@example.com")
    os.environ.setdefault("TEST_EMAIL_RECIPIENT", "recipient@example.com")

    os.environ["MAILJET_API_KEY"] = "11"
    os.environ["MAILJET_SECRET_KEY"] = "11"
    os.environ["FILE_STORAGE_DEFAULT"] = (
        "django.core.files.storage.FileSystemStorage?location=/tmp/hde/storage/"
    )
    os.environ["FILE_STORAGE_STATIC"] = (
        "django.core.files.storage.FileSystemStorage?location=/tmp/hde/static/"
    )
    os.environ["FILE_STORAGE_MEDIA"] = (
        "django.core.files.storage.FileSystemStorage?location=/tmp/hde/storage/"
    )
    os.environ["FILE_STORAGE_HOPE"] = (
        "django.core.files.storage.FileSystemStorage?location=/tmp/hde/hope/"
    )
    os.environ["SOCIAL_AUTH_REDIRECT_IS_HTTPS"] = "0"
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "0"
    os.environ["SECURE_HSTS_PRELOAD"] = "0"
    os.environ["SECRET_KEY"] = "kugiugiuygiuygiuygiuhgiuhgiuhgiugiu"

    os.environ["GMAIL_USER"] = "11"
    os.environ["GMAIL_PASSWORD"] = "11"
    from django.conf import settings

    settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
    settings.MEDIA_ROOT = "/tmp/media"
    settings.STATIC_ROOT = "/tmp/static"
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    os.makedirs(settings.STATIC_ROOT, exist_ok=True)

    from django.core.management import CommandError, call_command

    django.setup()

    try:
        call_command("env", check=True)
    except CommandError:
        pytest.exit("FATAL: Environment variables missing")


@pytest.fixture(autouse=True)
def setup(db):
    from testutils.factories import GroupFactory

    GroupFactory(name=config.NEW_USER_DEFAULT_GROUP)


@pytest.fixture()
def mocked_responses():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps
