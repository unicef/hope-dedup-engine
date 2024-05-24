from io import BytesIO
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from hope_dedup_engine.apps.core.storage import CV2DNNStorage, HDEAzureStorage, HOPEAzureStorage
from hope_dedup_engine.apps.faces.utils.duplication_detector import DuplicationDetector

from ..faces_const import FILENAME


@pytest.fixture(scope="module", autouse=True)
def dd(mock_hope_azure_storage, mock_cv2dnn_storage, mock_hde_azure_storage):
    with (
        patch("hope_dedup_engine.apps.faces.utils.duplication_detector.CV2DNNStorage", mock_cv2dnn_storage),
        patch("hope_dedup_engine.apps.faces.utils.duplication_detector.HOPEAzureStorage", mock_hope_azure_storage),
        patch("hope_dedup_engine.apps.faces.utils.duplication_detector.HDEAzureStorage", mock_hde_azure_storage),
    ):
        mock_cv2dnn_storage.exists.return_value = False
        detector = DuplicationDetector(FILENAME)
        mock_logger = MagicMock()
        detector.logger = mock_logger
        return detector


@pytest.fixture(scope="module", autouse=True)
def mock_cv2dnn_storage():
    storage = MagicMock(spec=CV2DNNStorage)
    storage.exists.return_value = True
    storage.path.side_effect = lambda filename: FILENAME
    return storage


@pytest.fixture(scope="module", autouse=True)
def mock_hde_azure_storage():
    storage = MagicMock(spec=HDEAzureStorage)
    storage.exists.return_value = True
    # storage.listdir.return_value = (None, FILENAMES)
    storage.open.return_value.__enter__.return_value.read.return_value = b"binary image data"
    return storage


@pytest.fixture(scope="module", autouse=True)
def mock_hope_azure_storage():
    storage = MagicMock(spec=HOPEAzureStorage)
    storage.exists.return_value = True
    storage.open.return_value.__enter__.return_value.read.return_value = b"binary image data"
    return storage


@pytest.fixture
def image_bytes_io(dd):
    # Create an image and save it to a BytesIO object
    image = Image.new("RGB", (100, 100), color="red")
    img_byte_arr = BytesIO()
    image.save(img_byte_arr, format="JPEG")
    img_byte_arr.seek(0)

    def fake_open(file, mode="rb", *args, **kwargs):
        if "rb" in mode and file == dd.filename:
            # Return a new BytesIO object with image data each time to avoid file closure
            return BytesIO(img_byte_arr.getvalue())
        else:
            # Return a MagicMock for other cases to simulate other file behaviors
            return MagicMock()

    img_byte_arr.fake_open = fake_open

    return img_byte_arr


@pytest.fixture
def mock_open_context_manager(image_bytes_io):
    mock_open_context_manager = MagicMock()
    mock_open_context_manager.__enter__.return_value = image_bytes_io
    return mock_open_context_manager


@pytest.fixture
def mock_net():
    mock_net = MagicMock()  # Mocking the neural network object
    mock_detections = np.array(
        [
            [
                [
                    [0, 0, 0.95, 0.1, 0.1, 0.2, 0.2],  # with confidence 0.95
                    [0, 0, 0.15, 0.1, 0.1, 0.2, 0.2],  # with confidence 0.15
                ]
            ]
        ],
        dtype=np.float32,
    )  # Mocking the detections array
    expected_regions = [(10, 10, 20, 20)]  # Mocking the expected regions
    mock_net.forward.return_value = mock_detections  # Setting up the forward method of the mock network
    mock_imdecode = MagicMock(return_value=np.ones((100, 100, 3), dtype=np.uint8))
    mock_resize = MagicMock(return_value=np.ones((300, 300, 3), dtype=np.uint8))
    mock_blob = np.zeros((1, 3, 300, 300))
    return mock_net, mock_imdecode, mock_resize, mock_blob, expected_regions
