from unittest.mock import patch

import pytest

import docker


@pytest.fixture(scope="session")
def docker_client():
    client = docker.from_env()
    yield client
    client.close()


@pytest.fixture
def mock_redis_client():
    with patch("redis.Redis.set") as mock_set, patch("redis.Redis.delete") as mock_delete:
        yield mock_set, mock_delete


@pytest.fixture
def mock_duplication_detector():
    with patch(
        "hope_dedup_engine.apps.faces.utils.duplication_detector.DuplicationDetector.find_duplicates"
    ) as mock_find:
        yield mock_find
