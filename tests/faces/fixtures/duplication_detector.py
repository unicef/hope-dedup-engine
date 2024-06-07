from io import BytesIO
from unittest.mock import MagicMock, mock_open, patch

import cv2
import numpy as np
import pytest
from PIL import Image

from hope_dedup_engine.apps.core.storage import CV2DNNStorage, HDEAzureStorage, HOPEAzureStorage
from hope_dedup_engine.apps.faces.utils.duplication_detector import DuplicationDetector

from ..faces_const import (
    BLOB_SHAPE,
    DEPLOY_PROTO_CONTENT,
    FACE_DETECTIONS,
    FACE_REGIONS_VALID,
    FILENAMES,
    IGNORE_PAIRS,
    IMAGE_SIZE,
    RESIZED_IMAGE_SIZE,
)


@pytest.fixture
def dd(mock_hope_azure_storage, mock_cv2dnn_storage, mock_hde_azure_storage, mock_prototxt_file, db):
    with (
        patch("hope_dedup_engine.apps.faces.utils.duplication_detector.CV2DNNStorage", mock_cv2dnn_storage),
        patch("hope_dedup_engine.apps.faces.utils.duplication_detector.HOPEAzureStorage", mock_hope_azure_storage),
        patch("hope_dedup_engine.apps.faces.utils.duplication_detector.HDEAzureStorage", mock_hde_azure_storage),
        patch("builtins.open", mock_prototxt_file),
    ):
        return DuplicationDetector(FILENAMES, IGNORE_PAIRS)


@pytest.fixture
def mock_prototxt_file():
    return mock_open(read_data=DEPLOY_PROTO_CONTENT)


@pytest.fixture
def mock_cv2dnn_storage():
    return MagicMock(spec=CV2DNNStorage)


@pytest.fixture
def mock_hde_azure_storage():
    return MagicMock(spec=HDEAzureStorage)


@pytest.fixture
def mock_hope_azure_storage():
    return MagicMock(spec=HOPEAzureStorage)


@pytest.fixture
def image_bytes_io(dd):
    img_byte_arr = BytesIO()
    image = Image.new("RGB", (100, 100), color="red")
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
def mock_net():
    mock_net = MagicMock(spec=cv2.dnn_Net)  # Mocking the neural network object
    mock_detections = np.array([[FACE_DETECTIONS]], dtype=np.float32)  # Mocking the detections array
    mock_expected_regions = FACE_REGIONS_VALID
    mock_net.forward.return_value = mock_detections  # Setting up the forward method of the mock network
    mock_imdecode = MagicMock(return_value=np.ones(IMAGE_SIZE, dtype=np.uint8))
    mock_resize = MagicMock(return_value=np.ones(RESIZED_IMAGE_SIZE, dtype=np.uint8))
    mock_blob = np.zeros(BLOB_SHAPE)
    return mock_net, mock_imdecode, mock_resize, mock_blob, mock_expected_regions
