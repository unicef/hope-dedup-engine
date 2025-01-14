from unittest.mock import mock_open, patch

from django.core.exceptions import ValidationError

import face_recognition
import numpy as np
import pytest
from faces_const import DEPLOY_PROTO_SHAPE, FILENAME, FILENAME_ENCODED

from hope_dedup_engine.apps.api.deduplication.config import (
    DetectionConfig,
    RecognitionConfig,
)
from hope_dedup_engine.apps.faces.managers import DNNInferenceManager, StorageManager
from hope_dedup_engine.apps.faces.services.image_processor import BlobFromImageConfig


def test_init_successful(
    mock_net_manager: DNNInferenceManager, mock_image_processor, mock_config_defaults
):
    assert isinstance(mock_image_processor.storages, StorageManager)
    assert mock_image_processor.net is mock_net_manager
    assert isinstance(mock_image_processor.cfg_detection, DetectionConfig)
    assert isinstance(mock_image_processor.cfg_recognition, RecognitionConfig)
    assert isinstance(mock_image_processor.blob_from_image_cfg, BlobFromImageConfig)


def test_get_shape_valid(mock_prototxt_file, mock_config_defaults):
    with patch("builtins.open", mock_prototxt_file):
        config = BlobFromImageConfig(
            scale_factor=mock_config_defaults.detection.blob_from_image_scale_factor,
            mean_values=mock_config_defaults.detection.blob_from_image_mean_values,
            prototxt_path="test.prototxt",
        )
        shape = config._get_shape()
        assert shape == DEPLOY_PROTO_SHAPE


def test_get_shape_invalid(mock_config_defaults):
    with patch("builtins.open", mock_open(read_data="invalid_prototxt_content")):
        with pytest.raises(ValidationError):
            BlobFromImageConfig(
                scale_factor=mock_config_defaults.detection.blob_from_image_scale_factor,
                mean_values=mock_config_defaults.detection.blob_from_image_mean_values,
                prototxt_path="test.prototxt",
            )._get_shape()


def test_get_face_detections_dnn_with_detections(
    mock_image_processor, mock_net, mock_open_context_manager, mock_config_defaults
):
    dnn, imdecode, resize, _, expected_regions = mock_net
    with (
        patch("cv2.imdecode", imdecode),
        patch("cv2.resize", resize),
        patch.object(
            mock_image_processor.storages.get_storage("images"),
            "open",
            return_value=mock_open_context_manager,
        ),
        patch.object(mock_image_processor, "net", dnn),
    ):
        detections = mock_image_processor._get_face_detections_dnn(FILENAME)
    assert detections == expected_regions
    for region in detections:
        assert isinstance(region, tuple)
        assert len(region) == 4
        assert all(isinstance(coord, np.int64) for coord in region)


def test_get_face_detections_dnn_no_detections(mock_image_processor):
    with (
        patch.object(mock_image_processor, "_get_face_detections_dnn", return_value=[]),
    ):
        face_regions = mock_image_processor._get_face_detections_dnn()
        assert len(face_regions) == 0


def test_get_face_detections_dnn_exception(
    mock_image_processor, mock_open_context_manager
):
    with (
        patch.object(
            mock_image_processor.storages.get_storage("images"),
            "open",
            return_value=mock_open_context_manager,
        ),
        patch.object(mock_open_context_manager, "read", return_value=b"fake_data"),
        patch("cv2.imdecode", side_effect=TypeError("Test exception")),
    ):
        with pytest.raises(TypeError, match="Test exception"):
            mock_image_processor._get_face_detections_dnn(FILENAME)


@pytest.mark.parametrize("face_regions_validity", ["valid", "invalid"])
def test_encode_face(
    mock_image_processor, image_bytes_io, mock_face_detections, face_regions_validity
):
    __, face_regions_valid, face_regions_invalid = mock_face_detections
    face_regions = (
        face_regions_valid if face_regions_validity == "valid" else face_regions_invalid
    )

    with (
        patch.object(
            mock_image_processor.storages.get_storage("images"),
            "open",
            side_effect=image_bytes_io.fake_open,
        ) as mocked_image_open,
        patch.object(
            mock_image_processor.storages.get_storage("encoded"),
            "open",
            side_effect=image_bytes_io.fake_open,
        ) as mocked_encoded_open,
        patch.object(
            mock_image_processor, "_get_face_detections_dnn", return_value=face_regions
        ) as mock_get_face_detections_dnn,
        patch.object(face_recognition, "face_encodings") as mock_face_encodings,
    ):
        mock_image_processor.encode_face(FILENAME, FILENAME_ENCODED)

        mock_get_face_detections_dnn.assert_called_once()
        mocked_image_open.assert_called_with(FILENAME, "rb")
        assert mocked_image_open.side_effect == image_bytes_io.fake_open

        if face_regions_validity == "valid":
            mocked_encoded_open.assert_called_with(FILENAME_ENCODED, "wb")
            assert mocked_encoded_open.side_effect == image_bytes_io.fake_open
            mock_face_encodings.assert_called()
        else:
            mocked_encoded_open.assert_not_called()
            mock_face_encodings.assert_not_called()


@pytest.mark.parametrize(
    "method, exception_str",
    ((str("face_encodings"), "Test face_encodings exception"),),
)
def test_encode_face_exception_handling(
    mock_image_processor, mock_net, method: str, exception_str
):
    dnn, imdecode, *_ = mock_net
    with (
        pytest.raises(Exception, match=exception_str),
        patch.object(
            face_recognition, method, side_effect=Exception(exception_str)
        ) as mock_exception,
        patch.object(mock_image_processor, "net", dnn),
        patch("cv2.imdecode", imdecode),
        patch.object(mock_image_processor.logger, "exception") as mock_logger_exception,
    ):
        mock_image_processor.encode_face(FILENAME, FILENAME_ENCODED)

        mock_exception.assert_called_once()
        mock_logger_exception.assert_called_once()
