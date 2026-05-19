from io import BytesIO
from unittest.mock import MagicMock, mock_open, patch

import cv2
import numpy as np
import pytest
from PIL import Image
from django.contrib.auth import get_user_model
from django.test import Client
from docker import from_env
from freezegun import freeze_time
from pytest_mock import MockerFixture
from storages.backends.azure_storage import AzureStorage

from faces_const import (
    BLOB_SHAPE,
    DEPLOY_PROTO_CONTENT,
    DNN_FILE,
    FILENAMES,
    IMAGE_SIZE,
    RESIZED_IMAGE_SIZE,
)
from hope_dedup_engine.apps.faces.managers.file_sync import (
    AzureFileDownloader,
    GithubFileDownloader,
)


@pytest.fixture
def mock_dnn_azure_storage(mocker: MockerFixture):
    return MagicMock(spec=AzureStorage)


@pytest.fixture
def github_dnn_file_downloader():
    return GithubFileDownloader()


@pytest.fixture
def mock_requests_get():
    with patch("requests.get") as mock_get:
        mock_response = mock_get.return_value.__enter__.return_value
        mock_response.iter_content.return_value = DNN_FILE.get("content") * DNN_FILE.get("chunks")
        mock_response.raise_for_status = lambda: None
        yield mock_get


@pytest.fixture
def azure_dnn_file_downloader(mocker):
    downloader = AzureFileDownloader()
    mocker.patch.object(downloader.remote_storage, "exists", return_value=True)
    mock_remote_file = MagicMock()
    mocker.patch.object(downloader.remote_storage, "open", return_value=mock_remote_file)
    return downloader


@pytest.fixture
def local_path(tmp_path):
    return tmp_path / DNN_FILE.get("name")


@pytest.fixture
def mock_prototxt_file():
    return mock_open(read_data=DEPLOY_PROTO_CONTENT)


@pytest.fixture
def image_bytes_io():
    img_byte_arr = BytesIO()
    image = Image.new("RGB", (300, 300), color="red")
    image.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_byte_arr.fake_open = lambda *_: BytesIO(img_byte_arr.getvalue())
    return img_byte_arr


@pytest.fixture
def mock_open_context_manager(image_bytes_io):
    mock_open_context_manager = MagicMock()
    mock_open_context_manager.__enter__.return_value = image_bytes_io
    return mock_open_context_manager


@pytest.fixture
def mock_face_detections(mock_config_defaults):
    conf = mock_config_defaults.detection.confidence
    face_detections = np.array(
        [
            [
                [
                    (0, 0, conf + 0.01, 0.1, 0.1, 0.2, 0.2),
                    (0, 0, conf + 0.1, 0.3, 0.3, 0.4, 0.4),
                    (0, 0, conf - 0.01, 0.1, 0.1, 0.2, 0.2),
                ]
            ]
        ],
        dtype=np.float32,
    )
    face_regions_valid = [
        (120, 120, 160, 160),
        (40, 40, 80, 80),
    ]
    face_regions_invalid = [[], [(0, 0, 10)]]
    return face_detections, face_regions_valid, face_regions_invalid


@pytest.fixture
def mock_net(mock_face_detections):
    mock_net = MagicMock(spec=cv2.dnn_Net)  # Mocking the neural network object
    mock_detections, mock_expected_regions, _ = mock_face_detections
    mock_net.forward.return_value = mock_detections  # Setting up the forward method of the mock network
    mock_imdecode = MagicMock(return_value=np.ones(IMAGE_SIZE, dtype=np.uint8))
    mock_resize = MagicMock(return_value=np.ones(RESIZED_IMAGE_SIZE, dtype=np.uint8))
    mock_blob = np.zeros(BLOB_SHAPE)
    return mock_net, mock_imdecode, mock_resize, mock_blob, mock_expected_regions


@pytest.fixture(scope="session")
def docker_client():
    client = from_env()
    yield client
    client.close()


@pytest.fixture
def mock_redis_client():
    with (
        patch("redis.Redis.set") as mock_set,
        patch("redis.Redis.delete") as mock_delete,
    ):
        yield mock_set, mock_delete


@pytest.fixture
def mock_dd_find():
    with patch(
        "hope_dedup_engine.apps.faces.services.duplication_detector.DuplicationDetector.find_duplicates"
    ) as mock_find:
        mock_find.return_value = [
            FILENAMES[:2],
        ]  # Assuming the first two are duplicates based on mock data
        yield mock_find


@pytest.fixture
def time_control():
    with freeze_time("2024-01-01") as frozen_time:
        yield frozen_time


@pytest.fixture
def mock_file_sync_manager():
    with patch("hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager") as mock_file_sync_manager_class:
        mock_manager_instance = mock_file_sync_manager_class.return_value
        mock_downloader = MagicMock()
        mock_manager_instance.downloader = mock_downloader
        yield mock_manager_instance


@pytest.fixture
def admin_user(db):
    user_model = get_user_model()
    return user_model.objects.create_superuser(username="admin", password="admin", email="admin@example.com")


@pytest.fixture
def client(admin_user):
    client = Client()
    client.force_login(admin_user)
    return client
