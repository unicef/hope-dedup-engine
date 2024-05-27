import os
from unittest.mock import MagicMock, mock_open, patch

from django.conf import settings

import cv2
import numpy as np
import pytest
from constance import config
from faces_const import DEPLOY_PROTO_SHAPE, FACE_REGIONS_INVALID, FILENAME, FILENAME_ENCODED_FORMAT, FILENAMES

from hope_dedup_engine.apps.faces.utils.duplication_detector import DuplicationDetector


def test_duplication_detector_initialization(dd):
    assert isinstance(dd.net, cv2.dnn_Net)
    assert dd.filenames == FILENAMES
    assert dd.face_detection_confidence == config.FACE_DETECTION_CONFIDENCE
    assert dd.distance_threshold == config.FACE_DISTANCE_THRESHOLD
    assert dd.nms_threshold == config.NMS_THRESHOLD

    assert isinstance(dd.blob_from_image_cfg, DuplicationDetector.BlobFromImageConfig)
    assert dd.blob_from_image_cfg.scale_factor == config.BLOB_FROM_IMAGE_SCALE_FACTOR
    if isinstance(config.BLOB_FROM_IMAGE_MEAN_VALUES, str):
        expected_mean_values = tuple(map(float, config.BLOB_FROM_IMAGE_MEAN_VALUES.split(", ")))
    else:
        expected_mean_values = config.BLOB_FROM_IMAGE_MEAN_VALUES
    assert dd.blob_from_image_cfg.mean_values == expected_mean_values

    assert isinstance(dd.face_encodings_cfg, DuplicationDetector.FaceEncodingsConfig)
    assert dd.face_encodings_cfg.num_jitters == config.FACE_ENCODINGS_NUM_JITTERS
    assert dd.face_encodings_cfg.model == config.FACE_ENCODINGS_MODEL


def test_get_shape(dd, mock_prototxt_file):
    with patch("builtins.open", mock_prototxt_file):
        shape = dd._get_shape()
        assert shape == DEPLOY_PROTO_SHAPE


def test_set_net(dd, mock_cv2dnn_storage, mock_net):
    mock_net_instance, *_ = mock_net
    with patch("cv2.dnn.readNetFromCaffe", return_value=mock_net_instance) as mock_read_net:
        net = dd._set_net(mock_cv2dnn_storage)
        mock_read_net.assert_called_once_with(
            mock_cv2dnn_storage.path(settings.PROTOTXT_FILE),
            mock_cv2dnn_storage.path(settings.CAFFEMODEL_FILE),
        )

        assert net == mock_net_instance
        mock_net_instance.setPreferableBackend.assert_called_once_with(int(config.DNN_BACKEND))
        mock_net_instance.setPreferableTarget.assert_called_once_with(int(config.DNN_TARGET))

    for storage_name, storage in dd.storages.items():
        assert isinstance(storage, MagicMock)
        if storage_name == "cv2dnn":
            storage.exists.assert_any_call(settings.PROTOTXT_FILE)
            storage.exists.assert_any_call(settings.CAFFEMODEL_FILE)
            storage.path.assert_any_call(settings.PROTOTXT_FILE)
            storage.path.assert_any_call(settings.CAFFEMODEL_FILE)


@pytest.mark.parametrize(
    "ignore_input, expected_output",
    [
        (tuple(), set()),
        ((("file1.jpg", "file2.jpg"),), {("file1.jpg", "file2.jpg"), ("file2.jpg", "file1.jpg")}),
        (
            (("file1.jpg", "file2.jpg"), ("file2.jpg", "file1.jpg")),
            {("file1.jpg", "file2.jpg"), ("file2.jpg", "file1.jpg")},
        ),
        (
            (("file1.jpg", "file3.jpg"), ("file2.jpg", "file3.jpg")),
            {
                ("file1.jpg", "file3.jpg"),
                ("file3.jpg", "file1.jpg"),
                ("file2.jpg", "file3.jpg"),
                ("file3.jpg", "file2.jpg"),
            },
        ),
    ],
)
def test_get_pairs_to_ignore_success(mock_cv2dnn_storage, mock_prototxt_file, ignore_input, expected_output):
    with (
        patch("hope_dedup_engine.apps.faces.utils.duplication_detector.CV2DNNStorage", mock_cv2dnn_storage),
        patch("builtins.open", mock_prototxt_file),
    ):
        dd = DuplicationDetector(FILENAMES, ignore_input)
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
def test_get_pairs_to_ignore_exception_handling(mock_cv2dnn_storage, mock_prototxt_file, ignore_input):
    with (
        pytest.raises(ValueError),
        patch("hope_dedup_engine.apps.faces.utils.duplication_detector.CV2DNNStorage", mock_cv2dnn_storage),
        patch("builtins.open", mock_prototxt_file),
    ):
        DuplicationDetector(filenames=FILENAMES, ignore_pairs=ignore_input)


@pytest.mark.parametrize("missing_file", [settings.PROTOTXT_FILE, settings.CAFFEMODEL_FILE])
def test_initialization_missing_files_in_cv2dnn_storage(mock_cv2dnn_storage, missing_file):
    with (
        pytest.raises(FileNotFoundError),
        patch("hope_dedup_engine.apps.faces.utils.duplication_detector.CV2DNNStorage", mock_cv2dnn_storage),
    ):
        mock_cv2dnn_storage.exists.side_effect = lambda filename: filename != missing_file
        DuplicationDetector(FILENAME)
        mock_cv2dnn_storage.exists.assert_any_call(missing_file)


def test_encodings_filename(dd):
    assert dd._encodings_filename(FILENAME) == FILENAME_ENCODED_FORMAT.format(FILENAME)


@pytest.mark.parametrize("file_exists", [True, False])
def test_has_encodings(dd, file_exists):
    dd.storages["encoded"].exists.return_value = file_exists
    assert dd._has_encodings(FILENAME) == file_exists
    dd.storages["encoded"].exists.assert_called_with(FILENAME_ENCODED_FORMAT.format(FILENAME))


def test_get_face_detections_dnn_no_detections(dd, mock_open_context_manager):
    with (
        patch.object(dd.storages["images"], "open", return_value=mock_open_context_manager),
        patch.object(dd, "_get_face_detections_dnn", return_value=[]),
    ):
        face_regions = dd._get_face_detections_dnn()
        assert len(face_regions) == 0


def test_get_face_detections_dnn_with_detections(dd, mock_net, mock_open_context_manager):
    net, imdecode, resize, _, expected_regions = mock_net
    with (
        patch.object(dd.storages["images"], "open", return_value=mock_open_context_manager),
        patch("cv2.imdecode", imdecode),
        patch("cv2.resize", resize),
        patch.object(dd, "net", net),
    ):
        face_regions = dd._get_face_detections_dnn(FILENAME)

        assert face_regions == expected_regions
        for region in face_regions:
            assert isinstance(region, tuple)
            assert len(region) == 4


def test_get_face_detections_dnn_exception_handling(dd):
    with (
        pytest.raises(Exception, match="Test exception"),
        patch.object(dd.storages["images"], "open", side_effect=Exception("Test exception")) as mock_storage_open,
        patch.object(dd.logger, "exception") as mock_logger_exception,
    ):
        dd._get_face_detections_dnn(FILENAME)

        mock_storage_open.assert_called_once_with(FILENAME, "rb")
        mock_logger_exception.assert_called_once()


@pytest.mark.parametrize(
    "filenames, expected", [(FILENAMES, {filename: np.array([1, 2, 3]) for filename in FILENAMES}), ([], {})]
)
def test_load_encodings_all_files(dd, filenames, expected):
    mock_encoded_data = {FILENAME_ENCODED_FORMAT.format(filename): np.array([1, 2, 3]) for filename in filenames}

    with (
        patch.object(
            dd.storages["encoded"],
            "listdir",
            return_value=(None, [FILENAME_ENCODED_FORMAT.format(filename) for filename in filenames]),
        ),
        patch("builtins.open", mock_open()) as mocked_open,
        patch("numpy.load") as mock_load,
    ):

        mocked_files_read = {
            filename: mock_open(read_data=data.tobytes()).return_value for filename, data in mock_encoded_data.items()
        }
        mocked_open.side_effect = lambda f, mode="rb": mocked_files_read[os.path.basename(f)]

        for filename, data in mock_encoded_data.items():
            mock_load.side_effect = lambda f, data=data, filename=filename, allow_pickle=False: (
                data if f.name.endswith(filename) else MagicMock()
            )

        result = dd._load_encodings_all()

        if filenames:
            for key, value in expected.items():
                assert np.array_equal(result[key], value)
        else:
            assert result == expected


def test_load_encodings_all_exception_handling_listdir(dd):
    with (
        pytest.raises(Exception, match="Test exception"),
        patch.object(dd.storages["encoded"], "listdir", side_effect=Exception("Test exception")) as mock_listdir,
        patch.object(dd.logger, "exception") as mock_logger_exception,
    ):
        dd._load_encodings_all()

        mock_listdir.assert_called_once_with("")
        mock_logger_exception.assert_called_once()


def test_load_encodings_all_exception_handling_open(dd):
    with (
        pytest.raises(Exception, match="Test exception"),
        patch.object(
            dd.storages["encoded"], "listdir", return_value=(None, [FILENAME_ENCODED_FORMAT.format(FILENAME)])
        ) as mock_listdir,
        patch.object(dd.storages["encoded"], "open", side_effect=Exception("Test exception")) as mock_open,
        patch.object(dd.logger, "exception") as mock_logger_exception,
    ):
        dd._load_encodings_all()

        mock_listdir.assert_called_once_with("")
        mock_open.assert_called_once_with(FILENAME_ENCODED_FORMAT.format(FILENAME), "rb")
        mock_logger_exception.assert_called_once()


def test_encode_face_successful(dd, image_bytes_io, mock_net):
    mock_net, *_ = mock_net
    with (
        patch.object(dd.storages["images"], "open", side_effect=image_bytes_io.fake_open) as mocked_image_open,
        patch.object(dd, "net", mock_net),
    ):
        dd._encode_face(FILENAME)

        mocked_image_open.assert_called_with(FILENAME, "rb")
        assert mocked_image_open.side_effect == image_bytes_io.fake_open
        assert mocked_image_open.called


@pytest.mark.parametrize("face_regions", FACE_REGIONS_INVALID)
def test_encode_face_error(dd, image_bytes_io, face_regions):
    with (
        patch.object(dd.storages["images"], "open", side_effect=image_bytes_io.fake_open) as mock_storage_open,
        patch.object(dd, "_get_face_detections_dnn", return_value=face_regions) as mock_get_face_detections_dnn,
        patch.object(dd.logger, "error") as mock_error_logger,
    ):
        dd._encode_face(FILENAME)

        mock_storage_open.assert_called_with(FILENAME, "rb")
        mock_get_face_detections_dnn.assert_called_once()

        mock_error_logger.assert_called_once()


def test_encode_face_exception_handling(dd):
    with (
        pytest.raises(Exception, match="Test exception"),
        patch.object(dd.storages["images"], "open", side_effect=Exception("Test exception")) as mock_storage_open,
        patch.object(dd.logger, "exception") as mock_logger_exception,
    ):
        dd._encode_face(FILENAME)

        mock_storage_open.assert_called_with(FILENAME, "rb")
        mock_logger_exception.assert_called_once()


def test_find_duplicates_successful_when_encoded(dd, mock_hde_azure_storage):
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
        expected_duplicates = (tuple(FILENAMES),)
        assert {frozenset(t) for t in duplicates} == {frozenset(t) for t in expected_duplicates}

        dd._encode_face.assert_not_called()
        dd._load_encodings_all.assert_called_once()
        mock_hde_azure_storage.exists.assert_called_with(FILENAME_ENCODED_FORMAT.format(FILENAMES[-1]))


def test_find_duplicates_no_encodings(dd):
    with (
        patch.object(dd, "_has_encodings", return_value=False),
        patch.object(dd, "_encode_face") as mock_encode_face,
        patch.object(dd, "_load_encodings_all", return_value={}) as mock_load_encodings,
    ):

        dd.find_duplicates()

        mock_encode_face.assert_called_with(FILENAMES[-1])
        mock_load_encodings.assert_called_once()


def test_find_duplicates_exception_handling(dd):
    with (
        pytest.raises(Exception, match="Test exception"),
        patch.object(dd, "_load_encodings_all", side_effect=Exception("Test exception")),
        patch.object(dd.logger, "exception") as mock_logger_exception,
    ):
        dd.find_duplicates()

        mock_logger_exception.assert_called_once()
