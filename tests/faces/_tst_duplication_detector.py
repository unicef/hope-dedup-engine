import os
from io import BytesIO
from unittest.mock import patch

from django.core.exceptions import ValidationError

import numpy as np
import pytest

from hope_dedup_engine.apps.faces.managers import StorageManager
from hope_dedup_engine.apps.faces.services import DuplicationDetector
from hope_dedup_engine.apps.faces.services.image_processor import ImageProcessor
from tests.faces._faces_const import FILENAME, FILENAME_ENCODED_FORMAT, FILENAMES


def test_init_successful(mock_dd, mock_config_defaults):
    assert mock_dd.filenames == FILENAMES
    assert mock_dd.face_distance_threshold == mock_config_defaults.duplicates.tolerance
    assert isinstance(mock_dd.storages, StorageManager)
    assert isinstance(mock_dd.image_processor, ImageProcessor)


@pytest.mark.parametrize(
    ("ignore_input", "expected_output"),
    [
        ([], set()),
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
    mock_storage_manager,
    mock_image_processor,
    mock_config_defaults,
    ignore_input,
    expected_output,
):
    dd = DuplicationDetector(FILENAMES, mock_config_defaults, ignore_input)
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
    mock_storage_manager, mock_image_processor, mock_config_defaults, ignore_input
):
    with pytest.raises(ValidationError):
        DuplicationDetector(FILENAMES, mock_config_defaults, ignore_pairs=ignore_input)


def test_encodings_filename(mock_dd):
    assert mock_dd._encodings_filename(FILENAME) == FILENAME_ENCODED_FORMAT.format(FILENAME)


@pytest.mark.parametrize("file_exists", [True, False])
def test_has_encodings(mock_dd, file_exists):
    with patch.object(mock_dd.storages.get_storage("encoded"), "exists") as file_exists_mock:
        file_exists_mock.return_value = file_exists
        assert mock_dd._has_encodings(FILENAME) == file_exists
        mock_dd.storages.get_storage("encoded").exists.assert_called_with(FILENAME_ENCODED_FORMAT.format(FILENAME))


def test_load_encodings_all_exception_handling_listdir(mock_dd):
    with (
        patch.object(
            mock_dd.storages.get_storage("encoded"),
            "listdir",
            side_effect=Exception("Test exception"),
        ) as mock_listdir,
        patch.object(mock_dd.logger, "exception") as mock_logger_exception,
    ):
        with pytest.raises(Exception, match="Test exception"):
            mock_dd._load_encodings_all()

        mock_listdir.assert_called_once_with("")
        mock_logger_exception.assert_called_once()


def test_load_encodings_all_exception_handling_open(mock_dd):
    with (
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
        with pytest.raises(Exception, match="Test exception"):
            mock_dd._load_encodings_all()

        mock_listdir.assert_called_once_with("")
        mock_open.assert_called_once_with(FILENAME_ENCODED_FORMAT.format(FILENAME), "rb")
        mock_logger_exception.assert_called_once()


@pytest.mark.parametrize(
    ("filenames", "expected"),
    [(FILENAMES, {filename: np.array([1, 2, 3]) for filename in FILENAMES}), ([], {})],
)
def test_load_encodings_all_files(mock_dd, filenames, expected):
    def open_mock(filename, mode="rb"):
        filename = os.path.basename(filename)
        if filename in mock_open_data:
            mock_open_data[filename].seek(0)
            return mock_open_data[filename]
        return BytesIO()

    mock_open_data = {FILENAME_ENCODED_FORMAT.format(filename): BytesIO() for filename in filenames}
    for data in mock_open_data.values():
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
        patch.object(mock_dd.storages.get_storage("encoded"), "open", side_effect=open_mock),
        patch.object(mock_dd, "_has_encodings", return_value=True),
    ):
        result = mock_dd._load_encodings_all()
        for key in expected:
            assert key in result
            assert np.array_equal(result[key], expected[key])


@pytest.mark.parametrize(
    ("has_encodings", "mock_encodings", "distance_offsets", "expected_duplicates_files"),
    [
        (
            True,
            {
                "test_file.jpg": [np.array([0.1, 0.2, 0.3])],
                "test_file2.jpg": [np.array([0.1, 0.25, 0.35])],
                "test_file3.jpg": [np.array([0.4, 0.5, 0.6])],
            },
            [0.04, 0.1, -0.04],
            [("test_file.jpg", "test_file2.jpg"), ("test_file.jpg", "test_file3.jpg")],
        ),
        (
            False,
            {},
            [],
            [],
        ),
    ],
)
def test_find_duplicates_successfull(
    mock_dd,
    mock_encoded_azure_storage,
    mock_hope_azure_storage,
    image_bytes_io,
    mock_config_defaults,
    has_encodings,
    mock_encodings,
    distance_offsets,
    expected_duplicates_files,
):
    tolerance = mock_config_defaults.duplicates.tolerance
    expected_duplicates = [
        (file1, file2, round(tolerance - offset, 5))
        for (file1, file2), offset in zip(expected_duplicates_files, distance_offsets, strict=False)
    ]

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
        patch.object(mock_dd, "_load_encodings_all", return_value=mock_encodings) as mock_load_encodings,
        patch.object(mock_dd.image_processor, "encode_face"),
        patch(
            "face_recognition.face_distance",
            side_effect=[np.array([tolerance - offset]) for offset in distance_offsets],
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
        patch.object(mock_dd, "_load_encodings_all", side_effect=Exception("Test exception")),
        patch.object(mock_dd.logger, "exception") as mock_logger_exception,
    ):
        with pytest.raises(Exception, match="Test exception"):
            list(mock_dd.find_duplicates())
        mock_logger_exception.assert_called_once()
