from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="session")
def docker_client():
    import docker

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


@pytest.fixture
def mock_task_model():
    with patch("hope_dedup_engine.apps.faces.models.TaskModel.objects.create") as mock_create:
        mock_instance = MagicMock()
        mock_create.return_value = mock_instance
        mock_instance.save = MagicMock()
        yield mock_create, mock_instance
