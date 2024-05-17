import os
import pickle
from unittest.mock import MagicMock, mock_open, patch

from django.conf import settings

import numpy as np
from const import FILENAME, FILENAMES

# def test_initialization(dd):
#     assert isinstance(dd.net, cv2.dnn_Net)
#     assert dd.confidence == settings.FACE_DETECTION_CONFIDENCE
#     assert dd.threshold == settings.DISTANCE_THRESHOLD
#     assert dd.filename == FILENAME
#     assert dd.encodings_filename == f"{FILENAME}.pkl"
#     # assert dd.storages["default"].location == str(settings.DATASET_PATH)
#     assert dd.storages["images"].location == str(settings.IMAGES_PATH)
#     assert dd.storages["encoded"].location == str(settings.ENCODED_PATH)


def test_has_encodings_false(dd):
    dd.storages["encoded"].exists = MagicMock(return_value=False)
    assert not dd.has_encodings


def test_has_encodings_true(dd):
    dd.storages["encoded"].exists = MagicMock(return_value=True)
    assert dd.has_encodings


def test_get_face_detections_dnn_no_detections(dd, mock_open_context_manager):
    with (
        patch.object(dd.storages["images"], "open", return_value=mock_open_context_manager),
        patch.object(dd, "_get_face_detections_dnn", return_value=[]),
    ):

        face_regions = dd._get_face_detections_dnn()
        assert len(face_regions) == 0  # Assuming no faces are detected


def test_get_face_detections_dnn_with_detections(dd, mock_net, mock_open_context_manager):
    net, imdecode, resize, blob, expected_regions = mock_net
    with (
        patch.object(dd.storages["images"], "open", return_value=mock_open_context_manager),
        patch("cv2.imdecode", imdecode),
        patch("cv2.resize", resize),
    ):

        dd.net.setInput(blob)
        dd.net = net
        face_regions = dd._get_face_detections_dnn()

        assert face_regions == expected_regions
        assert len(face_regions) == 1  # Assuming one face is detected
        assert isinstance(face_regions[0], tuple)  # Each detected face region should be a tuple
        assert len(face_regions[0]) == 4  # Each tuple should have four elements (coordinates of the bounding box)


def test_get_face_detections_dnn_exception_handling(dd):
    with patch("builtins.open", side_effect=Exception("Test exception")):
        try:
            dd._get_face_detections_dnn()
        except Exception:
            ...
        dd.logger.exception.assert_called_once()
        dd.logger.reset_mock()


def test_load_encodings_all_no_files(dd):
    with patch.object(dd.storages["encoded"], "listdir", return_value=(None, [])):
        encodings = dd._load_encodings_all()
        assert encodings == {}


def test_load_encodings_all_with_files(dd):
    # Mock the data that would be returned by the storage
    mock_encoded_data = {
        f"{settings.ENCODED_PATH}/{filename}.pkl": [np.array([1, 2, 3]), np.array([4, 5, 6])] for filename in FILENAMES
    }
    encoded_data = {os.path.splitext(key)[0]: value for key, value in mock_encoded_data.items()}

    # Mock the storage's listdir method to return the file names
    with patch.object(
        dd.storages["encoded"],
        "listdir",
        return_value=(None, [f"{settings.ENCODED_PATH}/{filename}.pkl" for filename in FILENAMES]),
    ):
        # Mock the storage's open method to return the data for each file
        with patch(
            "builtins.open",
            side_effect=lambda f, mode: mock_open(read_data=pickle.dumps(mock_encoded_data[f])).return_value,
        ):
            encodings = dd._load_encodings_all()

    # Assert that the returned encodings match the expected data
    assert all(np.array_equal(encodings[key], value) for key, value in encoded_data.items())


def test_load_encodings_all_exception_handling(dd):
    with patch("builtins.open", side_effect=Exception("Test exception")):
        try:
            dd._load_encodings_all()
        except Exception:
            ...
        dd.logger.exception.assert_called_once()
        dd.logger.reset_mock()


def test_encode_face_successful(dd, image_bytes_io):
    with (
        patch("builtins.open", new_callable=lambda: image_bytes_io.fake_open),
        patch.object(dd.storages["images"], "open", side_effect=image_bytes_io.fake_open) as mocked_image_open,
    ):
        dd._encode_face()

        # Checks that the file was opened correctly and in binary read mode
        mocked_image_open.assert_called_with(dd.filename, "rb")
        assert mocked_image_open.called, "The open function should be called"


def test_encode_face_invalid_region(dd, image_bytes_io):
    # Mock _get_face_detections_dnn to return an invalid region
    with (
        patch("builtins.open", new_callable=lambda: image_bytes_io.fake_open),
        patch.object(dd.storages["images"], "open", side_effect=image_bytes_io.fake_open),
        patch.object(dd, "_get_face_detections_dnn", return_value=[(0, 0, 10)]),
        patch.object(dd.logger, "error") as mock_error_logger,
    ):

        # Invoke the _encode_face method, expecting an error log due to an invalid region
        dd._encode_face()

        # Check that the error was logged with the correct message
        mock_error_logger.assert_called_once_with(f"Invalid face region {(0, 0, 10)}")


def test_encode_face_exception_handling(dd):
    with patch("builtins.open", side_effect=Exception("Test exception")):
        try:
            dd._encode_face()
        except Exception:
            ...
        dd.logger.exception.assert_called_once()
        dd.logger.reset_mock()


def test_find_duplicates_successful(dd, mock_storage):
    # Generate mock return values dynamically based on FILENAMES
    mock_encodings = {filename: [np.array([0.1, 0.2, 0.3 + i * 0.001])] for i, filename in enumerate(FILENAMES)}

    # Mocking internal methods and storages
    with (
        patch.object(dd, "storages", {"encoded": mock_storage}),
        patch.object(dd, "_encode_face"),
        patch.object(dd, "_load_encodings_all", return_value=mock_encodings),
        patch("face_recognition.face_distance", return_value=np.array([0.05])),
    ):

        duplicates = dd.find_duplicates()

        # Check that the correct list of duplicates is returned
        expected_duplicates = set(FILENAMES[:2])  # Assuming the first two are duplicates based on mock data
        assert all(name in duplicates for name in expected_duplicates)

        dd._encode_face.assert_not_called()
        dd._load_encodings_all.assert_called_once()
        mock_storage.exists.assert_called_once_with(f"{FILENAME}.pkl")


def test_find_duplicates_calls_encode_face_when_no_encodings(dd):
    # Prepare a mock for the 'exists' method used in the 'has_encodings' property
    with (
        patch.object(dd.storages["encoded"], "exists", return_value=False),
        patch.object(dd, "_encode_face") as mock_encode_face,
    ):

        dd.find_duplicates()

        mock_encode_face.assert_called_once()
        dd.logger.reset_mock()


def test_find_duplicates_exception_handling(dd):
    with patch.object(dd, "_load_encodings_all", side_effect=Exception("Test exception")):
        try:
            dd.find_duplicates()
        except Exception:
            ...
        dd.logger.exception.assert_called_once()
        dd.logger.reset_mock()
