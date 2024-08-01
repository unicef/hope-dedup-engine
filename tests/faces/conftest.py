from io import BytesIO
from unittest.mock import MagicMock, mock_open, patch

import cv2
import numpy as np
import pytest
from faces_const import (
    BLOB_SHAPE,
    DEPLOY_PROTO_CONTENT,
    DEPLOY_PROTO_SHAPE,
    DNN_FILE,
    FACE_DETECTIONS,
    FACE_REGIONS_VALID,
    FILENAMES,
    IGNORE_PAIRS,
    IMAGE_SIZE,
    RESIZED_IMAGE_SIZE,
)
from freezegun import freeze_time
from PIL import Image
from pytest_mock import MockerFixture

from docker import from_env
from hope_dedup_engine.apps.core.storage import (
    CV2DNNStorage,
    DNNAzureStorage,
    HDEAzureStorage,
    HOPEAzureStorage,
)
from hope_dedup_engine.apps.faces.managers import DNNInferenceManager, StorageManager
from hope_dedup_engine.apps.faces.managers.file_sync import (
    AzureFileDownloader,
    GithubFileDownloader,
)
from hope_dedup_engine.apps.faces.services.duplication_detector import (
    DuplicationDetector,
)
from hope_dedup_engine.apps.faces.services.image_processor import (
    BlobFromImageConfig,
    ImageProcessor,
)


@pytest.fixture
def mock_storage_manager(mocker: MockerFixture) -> StorageManager:
    mocker.patch.object(CV2DNNStorage, "exists", return_value=True)
    mocker.patch.object(HDEAzureStorage, "exists", return_value=True)
    mocker.patch.object(HOPEAzureStorage, "exists", return_value=True)
    yield StorageManager()


@pytest.fixture
def mock_hde_azure_storage():
    return MagicMock(spec=HDEAzureStorage)


@pytest.fixture
def mock_hope_azure_storage():
    return MagicMock(spec=HOPEAzureStorage)


@pytest.fixture
def mock_dnn_azure_storage():
    return MagicMock(spec=DNNAzureStorage)


@pytest.fixture
def github_dnn_file_downloader():
    return GithubFileDownloader()


@pytest.fixture
def azure_dnn_file_downloader(mock_dnn_azure_storage):
    return AzureFileDownloader(storage=mock_dnn_azure_storage)


@pytest.fixture
def mock_requests_get():
    with patch("requests.get") as mock_get:
        mock_response = mock_get.return_value.__enter__.return_value
        mock_response.iter_content.return_value = DNN_FILE.get(
            "content"
        ) * DNN_FILE.get("chunks")
        mock_response.raise_for_status = lambda: None
        yield mock_get


@pytest.fixture
def local_path(tmp_path):
    return tmp_path / DNN_FILE.get("name")


@pytest.fixture
def mock_prototxt_file():
    return mock_open(read_data=DEPLOY_PROTO_CONTENT)


@pytest.fixture
def mock_net_manager(mocker: MockerFixture) -> DNNInferenceManager:
    mock_net = mocker.Mock()
    mocker.patch("cv2.dnn.readNetFromCaffe", return_value=mock_net)
    yield mock_net


@pytest.fixture
def mock_image_processor(
    mocker: MockerFixture,
    mock_storage_manager,
    mock_net_manager,
    mock_open_context_manager,
) -> ImageProcessor:
    mocker.patch.object(
        BlobFromImageConfig, "_get_shape", return_value=DEPLOY_PROTO_SHAPE
    )
    mock_processor = ImageProcessor()
    mocker.patch.object(
        mock_processor.storages.get_storage("images"),
        "open",
        return_value=mock_open_context_manager,
    )
    yield mock_processor


@pytest.fixture
def image_bytes_io():
    img_byte_arr = BytesIO()
    image = Image.new("RGB", (100, 100), color="red")
    image.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)
    img_byte_arr.fake_open = lambda *_: BytesIO(img_byte_arr.getvalue())
    yield img_byte_arr


@pytest.fixture
def mock_open_context_manager(image_bytes_io):
    mock_open_context_manager = MagicMock()
    mock_open_context_manager.__enter__.return_value = image_bytes_io
    yield mock_open_context_manager


@pytest.fixture
def mock_net():
    mock_net = MagicMock(spec=cv2.dnn_Net)  # Mocking the neural network object
    mock_detections = np.array(
        [[FACE_DETECTIONS]], dtype=np.float32
    )  # Mocking the detections array
    mock_expected_regions = FACE_REGIONS_VALID
    mock_net.forward.return_value = (
        mock_detections  # Setting up the forward method of the mock network
    )
    mock_imdecode = MagicMock(return_value=np.ones(IMAGE_SIZE, dtype=np.uint8))
    mock_resize = MagicMock(return_value=np.ones(RESIZED_IMAGE_SIZE, dtype=np.uint8))
    mock_blob = np.zeros(BLOB_SHAPE)
    yield mock_net, mock_imdecode, mock_resize, mock_blob, mock_expected_regions


@pytest.fixture
def mock_dd(mock_image_processor, mock_net_manager, mock_storage_manager):
    detector = DuplicationDetector(FILENAMES, IGNORE_PAIRS)
    yield detector


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
    with patch(
        "hope_dedup_engine.apps.faces.celery_tasks.FileSyncManager"
    ) as MockFileSyncManager:
        mock_manager_instance = MockFileSyncManager.return_value
        mock_downloader = MagicMock()
        mock_manager_instance.downloader = mock_downloader
        yield mock_manager_instance
