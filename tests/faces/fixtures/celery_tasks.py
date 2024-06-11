from unittest.mock import patch

import pytest
from freezegun import freeze_time

from docker import from_env

from ..faces_const import FILENAMES


@pytest.fixture(scope="session")
def docker_client():
    client = from_env()
    yield client
    client.close()


@pytest.fixture
def mock_redis_client():
    with patch("redis.Redis.set") as mock_set, patch("redis.Redis.delete") as mock_delete:
        yield mock_set, mock_delete


@pytest.fixture
def mock_dd_find():
    with patch(
        "hope_dedup_engine.apps.faces.utils.duplication_detector.DuplicationDetector.find_duplicates"
    ) as mock_find:
        mock_find.return_value = (FILENAMES[:2],)  # Assuming the first two are duplicates based on mock data
        yield mock_find


@pytest.fixture
def time_control():
    with freeze_time("2024-01-01") as frozen_time:
        yield frozen_time
