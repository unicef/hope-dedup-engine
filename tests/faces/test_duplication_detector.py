import os
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ValidationError

import numpy as np
import pytest
from constance import config
from faces_const import (
    FACE_DISTANCE_THRESHOLD,
    FILENAME,
    FILENAME_ENCODED_FORMAT,
    FILENAMES,
)

from hope_dedup_engine.apps.faces.managers import StorageManager
from hope_dedup_engine.apps.faces.services import DuplicationDetector
from hope_dedup_engine.apps.faces.services.image_processor import ImageProcessor


def test_init_successful(mock_dd):
    assert mock_dd.filenames == FILENAMES
    assert isinstance(mock_dd.storages, StorageManager)
    assert isinstance(mock_dd.image_processor, ImageProcessor)
    assert (
        mock_dd.image_processor.face_detection_confidence
        == config.FACE_DETECTION_CONFIDENCE
    )
    assert mock_dd.image_processor.distance_threshold == config.FACE_DISTANCE_THRESHOLD
    assert mock_dd.image_processor.nms_threshold == config.NMS_THRESHOLD
    assert (
        mock_dd.image_processor.face_encodings_cfg.num_jitters
        == config.FACE_ENCODINGS_NUM_JITTERS
    )
    assert (
        mock_dd.image_processor.face_encodings_cfg.model == config.FACE_ENCODINGS_MODEL
    )
    assert (
        mock_dd.image_processor.blob_from_image_cfg.scale_factor
        == config.BLOB_FROM_IMAGE_SCALE_FACTOR
    )


@pytest.mark.parametrize(
    "ignore_input, expected_output",
    [
        (list(), set()),
        (
            [
                ["file1.jpg", "file2.jpg"],
            ],
            {("file1.jpg", "file2.jpg"), ("file2.jpg", "file1.jpg")},
        ),
        (
            [["file1.jpg", "file2.jpg"], ["file2.jpg", "file1.jpg"]],
            {("file1.jpg", "file2.jpg"), ("file2.jpg", "file1.jpg")},
        ),
        (
            [["file1.jpg", "file3.jpg"], ["file2.jpg", "file3.jpg"]],
            {
                ("file1.jpg", "file3.jpg"),
                ("file3.jpg", "file1.jpg"),
                ("file2.jpg", "file3.jpg"),
                ("file3.jpg", "file2.jpg"),
            },
        ),
    ],
)
def test_get_pairs_to_ignore_success(
    mock_storage_manager, mock_image_processor, ignore_input, expected_output
):
    dd = DuplicationDetector(FILENAMES, FACE_DISTANCE_THRESHOLD, ignore_input)
    assert dd.ignore_set == expected_output


@pytest.mark.parametrize(
    "ignore_input",
    [
        (("file1.jpg",),),
        (("file1.jpg", "file2.jpg", "file3.jpg"),),
        (
            "file1.jpg",
            "file2.jpg",
        ),
        ((1, "file2.jpg"),),
        (("", "file2.jpg"),),
    ],
)
def test_get_pairs_to_ignore_exception_handling(
    mock_storage_manager, mock_image_processor, ignore_input
):
    with pytest.raises(ValidationError):
        DuplicationDetector(FILENAMES, 0.2, ignore_pairs=ignore_input)


def test_encodings_filename(mock_dd):
    assert mock_dd._encodings_filename(FILENAME) == FILENAME_ENCODED_FORMAT.format(
        FILENAME
    )


@pytest.mark.parametrize("file_exists", [True, False])
def test_has_encodings(mock_dd, file_exists):
    with patch.object(
        mock_dd.storages.get_storage("encoded"), "exists"
    ) as file_exists_mock:
        file_exists_mock.return_value = file_exists
        assert mock_dd._has_encodings(FILENAME) == file_exists
        mock_dd.storages.get_storage("encoded").exists.assert_called_with(
            FILENAME_ENCODED_FORMAT.format(FILENAME)
        )


def test_load_encodings_all_exception_handling_listdir(mock_dd):
    with (
        pytest.raises(Exception, match="Test exception"),
        patch.object(
            mock_dd.storages.get_storage("encoded"),
            "listdir",
            side_effect=Exception("Test exception"),
        ) as mock_listdir,
        patch.object(mock_dd.logger, "exception") as mock_logger_exception,
    ):
        mock_dd._load_encodings_all()

        mock_listdir.assert_called_once_with("")
        mock_logger_exception.assert_called_once()


def test_load_encodings_all_exception_handling_open(mock_dd):
    with (
        pytest.raises(Exception, match="Test exception"),
        patch.object(
            mock_dd.storages.get_storage("encoded"),
            "listdir",
            return_value=(None, [FILENAME_ENCODED_FORMAT.format(FILENAME)]),
        ) as mock_listdir,
        patch.object(
            mock_dd.storages.get_storage("encoded"),
            "open",
            side_effect=Exception("Test exception"),
        ) as mock_open,
        patch.object(mock_dd.logger, "exception") as mock_logger_exception,
    ):
        mock_dd._load_encodings_all()

        mock_listdir.assert_called_once_with("")
        mock_open.assert_called_once_with(
            FILENAME_ENCODED_FORMAT.format(FILENAME), "rb"
        )
        mock_logger_exception.assert_called_once()


@pytest.mark.parametrize(
    "filenames, expected",
    [(FILENAMES, {filename: np.array([1, 2, 3]) for filename in FILENAMES}), ([], {})],
)
def test_load_encodings_all_files(mock_dd, filenames, expected):
    def open_mock(filename, mode="rb"):
        filename = os.path.basename(filename)
        if filename in mock_open_data:
            mock_open_data[filename].seek(0)
            return mock_open_data[filename]
        return BytesIO()

    mock_open_data = {
        FILENAME_ENCODED_FORMAT.format(filename): BytesIO() for filename in filenames
    }
    for _, data in mock_open_data.items():
        np.save(data, np.array([1, 2, 3]))
        data.seek(0)

    with (
        patch.object(
            mock_dd.storages.get_storage("encoded"),
            "listdir",
            return_value=(
                None,
                [FILENAME_ENCODED_FORMAT.format(filename) for filename in filenames],
            ),
        ),
        patch.object(
            mock_dd.storages.get_storage("encoded"), "open", side_effect=open_mock
        ),
        patch.object(mock_dd, "_has_encodings", return_value=True),
    ):
        result = mock_dd._load_encodings_all()
        for key in expected:
            assert key in result
            assert np.array_equal(result[key], expected[key])


@pytest.mark.parametrize(
    "has_encodings, mock_encodings, expected_duplicates",
    [
        (
            True,
            {
                "test_file.jpg": [np.array([0.1, 0.2, 0.3])],
                "test_file2.jpg": [np.array([0.1, 0.25, 0.35])],
                "test_file3.jpg": [np.array([0.4, 0.5, 0.6])],
            },
            [
                (
                    "test_file.jpg",
                    "test_file2.jpg",
                    0.36,
                ),  # config.FACE_DISTANCE_THRESHOLD + 0.04
                (
                    "test_file.jpg",
                    "test_file3.jpg",
                    0.2,
                ),  # config.FACE_DISTANCE_THRESHOLD - 0.2
                # last pair will not be included in the result because the distance is greater than the threshold
                # ("test_file2.jpg", "test_file3.jpg", 0.44), # config.FACE_DISTANCE_THRESHOLD + 0.04
            ],
        ),
        (
            False,
            {},
            (),
        ),
    ],
)
def test_find_duplicates_successful(
    mock_dd,
    mock_encoded_azure_storage,
    mock_hope_azure_storage,
    image_bytes_io,
    has_encodings,
    mock_encodings,
    expected_duplicates,
):
    with (
        patch.object(
            mock_dd.storages,
            "get_storage",
            side_effect=lambda key: {
                "encoded": mock_encoded_azure_storage,
                "images": mock_hope_azure_storage,
            }[key],
        ),
        patch.object(
            mock_dd.storages.get_storage("images"),
            "open",
            side_effect=image_bytes_io.fake_open,
        ),
        patch.object(
            mock_dd.storages.get_storage("images"),
            "listdir",
            return_value=([], FILENAMES),
        ),
        patch.object(
            mock_dd.storages.get_storage("encoded"),
            "open",
            side_effect=image_bytes_io.fake_open,
        ),
        patch.object(mock_dd, "_has_encodings", return_value=has_encodings),
        patch.object(
            mock_dd, "_load_encodings_all", return_value=mock_encodings
        ) as mock_load_encodings,
        patch.object(mock_dd.image_processor, "encode_face"),
        patch(
            "face_recognition.face_distance",
            side_effect=[
                np.array([config.FACE_DISTANCE_THRESHOLD - 0.04]),
                np.array([config.FACE_DISTANCE_THRESHOLD - 0.2]),
                np.array([config.FACE_DISTANCE_THRESHOLD + 0.04]),
            ],
        ),
    ):
        duplicates = list(mock_dd.find_duplicates())

        if has_encodings:
            assert duplicates == expected_duplicates
            mock_dd.image_processor.encode_face.assert_not_called()
            mock_dd._load_encodings_all.assert_called_once()
        else:
            mock_load_encodings.assert_called_once()
            mock_dd.image_processor.encode_face.assert_called()


def test_find_duplicates_exception_handling(
    mock_dd, mock_hope_azure_storage, mock_encoded_azure_storage, image_bytes_io
):
    with (
        pytest.raises(Exception, match="Test exception"),
        patch.object(
            mock_dd.storages,
            "get_storage",
            side_effect=lambda key: {
                "encoded": mock_encoded_azure_storage,
                "images": mock_hope_azure_storage,
            }[key],
        ),
        patch.object(
            mock_dd.storages.get_storage("images"),
            "listdir",
            return_value=([], FILENAMES),
        ),
        patch.object(
            mock_dd.storages.get_storage("images"),
            "open",
            side_effect=image_bytes_io.fake_open,
        ),
        patch.object(
            mock_dd, "_load_encodings_all", side_effect=Exception("Test exception")
        ),
        patch.object(mock_dd.logger, "exception") as mock_logger_exception,
    ):
        list(mock_dd.find_duplicates())
        mock_logger_exception.assert_called_once()
