import os
from unittest.mock import MagicMock, mock_open, patch

from django.conf import settings

import cv2
import numpy as np
import pytest
from constance import config
from faces_const import FILENAME, FILENAMES

from hope_dedup_engine.apps.faces.utils.duplication_detector import DuplicationDetector


def test_duplication_detector_initialization(dd):
    assert isinstance(dd.net, cv2.dnn_Net)
    assert isinstance(dd.logger, MagicMock)
    assert dd.face_detection_confidence == config.FACE_DETECTION_CONFIDENCE
    assert dd.distance_threshold == config.DISTANCE_THRESHOLD
    assert dd.filename == FILENAME
    assert dd.encodings_filename == f"{FILENAME}.npy"
    for storage_name, storage in dd.storages.items():
        assert isinstance(storage, MagicMock)
        if storage_name == "cv2dnn":
            storage.exists.assert_any_call(settings.PROTOTXT_FILE)
            storage.exists.assert_any_call(settings.CAFFEMODEL_FILE)
            storage.path.assert_any_call(settings.CAFFEMODEL_FILE)
            storage.path.assert_any_call(settings.CAFFEMODEL_FILE)


def test_missing_files_in_storage(dd, mock_cv2dnn_storage):
    with patch(
        "hope_dedup_engine.apps.faces.utils.duplication_detector.CV2DNNStorage", new=lambda _: mock_cv2dnn_storage
    ):
        mock_cv2dnn_storage.exists.return_value = False
        with pytest.raises(FileNotFoundError):
            DuplicationDetector(FILENAME)


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
    mock_encoded_data = {f"{filename}.npy": np.array([1, 2, 3]) for filename in FILENAMES}
    encoded_data = {os.path.splitext(key)[0]: value for key, value in mock_encoded_data.items()}

    with patch.object(
        dd.storages["encoded"], "listdir", return_value=(None, [f"{filename}.npy" for filename in FILENAMES])
    ):
        with patch("builtins.open", mock_open()) as mocked_open:
            for filename, data in mock_encoded_data.items():
                mocked_file = mock_open(read_data=data.tobytes()).return_value
                mocked_open.side_effect = lambda f, mode="rb", mocked_file=mocked_file, filename=filename: (
                    mocked_file if f.endswith(filename) else MagicMock()
                )
                with patch("numpy.load", return_value=data):
                    result = dd._load_encodings_all()

            for key, value in encoded_data.items():
                assert np.array_equal(result[key], value)


def test_load_encodings_all_exception_handling(dd):
    with patch("builtins.open", side_effect=Exception("Test exception")):
        try:
            dd._load_encodings_all()
        except Exception:
            ...
        dd.logger.reset_mock()


def test_encode_face_successful(dd, image_bytes_io, mock_net):
    mock_net, *_ = mock_net
    with (
        patch.object(dd.storages["images"], "open", side_effect=image_bytes_io.fake_open) as mocked_image_open,
        patch.object(dd, "net", mock_net),
    ):
        dd._encode_face()
        mocked_image_open.assert_called_with(dd.filename, "rb")
        assert mocked_image_open.called


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
        dd.logger.reset_mock()


def test_encode_face_exception_handling(dd):
    with patch("builtins.open", side_effect=Exception("Test exception")):
        try:
            dd._encode_face()
        except Exception:
            ...
        dd.logger.exception.assert_called_once()
        dd.logger.reset_mock()


def test_find_duplicates_successful(dd, mock_hde_azure_storage):
    # Generate mock return values dynamically based on FILENAMES
    mock_encodings = {filename: [np.array([0.1, 0.2, 0.3 + i * 0.001])] for i, filename in enumerate(FILENAMES)}

    # Mocking internal methods and storages
    with (
        patch.object(dd, "storages", {"encoded": mock_hde_azure_storage}),
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
        mock_hde_azure_storage.exists.assert_called_once_with(f"{FILENAME}.npy")


def test_find_duplicates_calls_encode_face_when_no_encodings(dd):
    with (
        patch(
            "hope_dedup_engine.apps.faces.utils.duplication_detector.DuplicationDetector.has_encodings",
            new_callable=MagicMock(return_value=False),
        ),
        patch.object(dd, "_encode_face") as mock_encode_face,
        patch.object(dd, "_load_encodings_all", return_value={"test_file.jpg": [MagicMock()]}),
    ):
        dd.find_duplicates()
        mock_encode_face.assert_called_once()


def test_find_duplicates_exception_handling(dd):
    with patch.object(dd, "_load_encodings_all", side_effect=Exception("Test exception")):
        try:
            dd.find_duplicates()
        except Exception:
            ...
        dd.logger.exception.assert_called_once()
        dd.logger.reset_mock()
