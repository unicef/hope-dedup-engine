from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from unittest.mock import MagicMock
    from pytest_mock import MockerFixture
    from rest_framework.test import APIClient


import pytest


@pytest.fixture
def anonymous_api_client() -> APIClient:
    from rest_framework.test import APIClient  # noqa: PLC0415

    return APIClient()


@pytest.fixture
def another_system_api_client(db: Any) -> APIClient:
    from api.utils import create_api_client  # noqa: PLC0415
    from testutils.factories.api import HDETokenFactory  # noqa: PLC0415
    from testutils.factories.user import SystemFactory, UserFactory  # noqa: PLC0415

    token = HDETokenFactory(user=UserFactory(), system=SystemFactory())
    return create_api_client(token)


@pytest.fixture
def delete_model_data(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.views.delete_model_data")


@pytest.fixture(autouse=True)
def send_notification(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("hope_dedup_engine.apps.api.deduplication.process.send_notification")


@pytest.fixture(scope="session")
def images_dir() -> Path:
    """Returns the absolute path to the test images directory."""
    return Path(__file__).parent.parent / "utils" / "images"


@pytest.fixture
def random_image_filename(images_dir: Path) -> str:
    """Returns a random filename from the test images directory."""
    files = [f for f in os.listdir(images_dir) if os.path.isfile(images_dir / f)]
    return random.choice(files)
