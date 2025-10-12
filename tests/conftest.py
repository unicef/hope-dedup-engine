from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import Client

import pytest
import responses
from constance import config

if TYPE_CHECKING:
    from rest_framework.test import APIClient
    from hope_dedup_engine.apps.api.models import (
        DeduplicationSet,
        HDEToken,
        Image,
        Finding,
        IgnoredFilenamePair,
        IgnoredReferencePkPair,
    )
    from hope_dedup_engine.apps.security.models import System, User
    from testutils.factories.api import (
        DedupJobFactory,
        FindingFactory,
        IgnoredFilenamePairFactory,
        IgnoredReferencePkPairFactory,
        ImageFactory,
    )


here = Path(__file__).parent
sys.path.insert(0, str(here / "../src"))
sys.path.insert(0, str(here / "extras"))


def pytest_configure(config):
    os.environ.update(DJANGO_SETTINGS_MODULE="hope_dedup_engine.config.settings")
    os.environ.setdefault("MEDIA_ROOT", "/tmp/static/")
    os.environ.setdefault("STATIC_ROOT", "/tmp/media/")
    os.environ.setdefault("DEFAULT_ROOT", "/tmp/default/")

    os.environ.setdefault("TEST_EMAIL_SENDER", "sender@example.com")
    os.environ.setdefault("TEST_EMAIL_RECIPIENT", "recipient@example.com")

    os.environ["MAILJET_API_KEY"] = "11"
    os.environ["MAILJET_SECRET_KEY"] = "11"
    os.environ["FILE_STORAGE_DEFAULT"] = "django.core.files.storage.FileSystemStorage?location=/tmp/hde/storage/"
    os.environ["FILE_STORAGE_STATIC"] = "django.core.files.storage.FileSystemStorage?location=/tmp/hde/static/"
    os.environ["FILE_STORAGE_MEDIA"] = "django.core.files.storage.FileSystemStorage?location=/tmp/hde/storage/"
    os.environ["FILE_STORAGE_HOPE"] = "django.core.files.storage.FileSystemStorage?location=/tmp/hde/hope/"
    os.environ["SOCIAL_AUTH_REDIRECT_IS_HTTPS"] = "0"
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "0"
    os.environ["SECURE_HSTS_PRELOAD"] = "0"
    os.environ["SECRET_KEY"] = "kugiugiuygiuygiuygiuhgiuhgiuhgiugiu"

    os.environ["GMAIL_USER"] = "11"
    os.environ["GMAIL_PASSWORD"] = "11"

    settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
    settings.MEDIA_ROOT = "/tmp/media"
    settings.STATIC_ROOT = "/tmp/static"
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    os.makedirs(settings.STATIC_ROOT, exist_ok=True)

    django.setup()

    try:
        call_command("env", check=True)
    except CommandError:
        pytest.exit("FATAL: Environment variables missing")


@pytest.fixture(autouse=True)
def setup(db):
    # we cannot import this at top-level of a file, because this import requires settings to be initialized. If moved
    # at top=level of a file, it produces the following
    #
    # django.core.exceptions.ImproperlyConfigured:
    # Requested setting USE_DEPRECATED_PYTZ, but settings are not configured. You must either define the environment
    # variable DJANGO_SETTINGS_MODULE or call settings.configure() before accessing settings.
    from testutils.factories import GroupFactory  # noqa: PLC0415

    GroupFactory(name=config.NEW_USER_DEFAULT_GROUP)


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture
def complex_deduplication_data():
    """Provide sample data for a complex deduplication scenario."""
    from hope_dedup_engine.apps.api.models import Image  # noqa: PLC0415

    return {
        "files0": (files := ["f1.jpg", "f2.jpg", "f3.jpg", "f4.jpg", "f5.jpg"]),
        "files1": files,
        "encodings": {
            "f1.jpg": [1.0],  # duplicate with f2
            "f2.jpg": [1.01],
            "f3.jpg": [2.0],  # not a duplicate with anyone
            "f4.jpg": Image.StatusCode.NO_FACE_DETECTED.value,  # error
            "f5.jpg": [1.02],  # ignored with f1
        },
        "ignored_pairs": {("f1.jpg", "f5.jpg")},
        "dedupe_threshold": 0.9,
    }


@pytest.fixture
def admin_user(db):
    user_model = get_user_model()
    return user_model.objects.create_superuser(username="admin", password="admin", email="admin@example.com")


@pytest.fixture
def client(admin_user):
    client = Client()
    client.force_login(admin_user)
    return client


@pytest.fixture
def system() -> "System":
    from testutils.factories.user import SystemFactory  # noqa: PLC0415

    return SystemFactory()


@pytest.fixture
def user() -> "User":
    from testutils.factories.user import UserFactory  # noqa: PLC0415

    return UserFactory()


@pytest.fixture
def hdetoken(user: "User", system: "System") -> "HDEToken":
    from testutils.factories.api import HDETokenFactory  # noqa: PLC0415

    return HDETokenFactory(user=user, system=system)


@pytest.fixture
def deduplication_set(system: "System") -> "DeduplicationSet":
    from testutils.factories.api import DeduplicationSetFactory  # noqa: PLC0415

    return DeduplicationSetFactory(system=system)


@pytest.fixture
def api_client(hdetoken: "HDEToken") -> "APIClient":
    from api.utils import create_api_client  # noqa: PLC0415

    return create_api_client(hdetoken)


@pytest.fixture
def dedup_job_factory() -> type[DedupJobFactory]:
    """Provides the DedupJobFactory class to tests."""
    from testutils.factories.api import DedupJobFactory  # noqa: PLC0415

    return DedupJobFactory


@pytest.fixture
def image_factory() -> type[ImageFactory]:
    """Provides the ImageFactory class to tests."""
    from testutils.factories.api import ImageFactory  # noqa: PLC0415

    return ImageFactory


@pytest.fixture
def finding_factory() -> type[FindingFactory]:
    """Provides the FindingFactory class to tests."""
    from testutils.factories.api import FindingFactory  # noqa: PLC0415

    return FindingFactory


@pytest.fixture
def ignored_filename_pair_factory() -> type[IgnoredFilenamePairFactory]:
    """Provides the IgnoredFilenamePairFactory class to tests."""
    from testutils.factories.api import IgnoredFilenamePairFactory  # noqa: PLC0415

    return IgnoredFilenamePairFactory


@pytest.fixture
def ignored_reference_pk_pair_factory() -> type[IgnoredReferencePkPairFactory]:
    """Provides the IgnoredReferencePkPairFactory class to tests."""
    from testutils.factories.api import IgnoredReferencePkPairFactory  # noqa: PLC0415

    return IgnoredReferencePkPairFactory


@pytest.fixture
def image(image_factory: type[ImageFactory], deduplication_set: "DeduplicationSet") -> "Image":
    """Provides an Image instance linked to a deduplication_set."""
    return image_factory(deduplication_set=deduplication_set)


@pytest.fixture
def finding(finding_factory: type[FindingFactory], deduplication_set: "DeduplicationSet") -> "Finding":
    """Provides a Finding instance linked to a deduplication_set."""
    return finding_factory(deduplication_set=deduplication_set)


@pytest.fixture
def ignored_filename_pair(
    ignored_filename_pair_factory: type[IgnoredFilenamePairFactory], deduplication_set: "DeduplicationSet"
) -> "IgnoredFilenamePair":
    """Provides an IgnoredFilenamePair instance linked to a deduplication_set."""
    return ignored_filename_pair_factory(deduplication_set=deduplication_set)


@pytest.fixture
def ignored_reference_pk_pair(
    ignored_reference_pk_pair_factory: type[IgnoredReferencePkPairFactory], deduplication_set: "DeduplicationSet"
) -> "IgnoredReferencePkPair":
    """Provides an IgnoredReferencePkPair instance linked to a deduplication_set."""
    return ignored_reference_pk_pair_factory(deduplication_set=deduplication_set)
