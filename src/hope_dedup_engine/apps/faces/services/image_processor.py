import logging
import re
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError

import cv2
import face_recognition
import numpy as np
from constance import config

from hope_dedup_engine.apps.faces.managers import DNNInferenceManager, StorageManager


@dataclass(frozen=True, slots=True)
class FaceEncodingsConfig:
    num_jitters: int
    model: str


@dataclass(frozen=True, slots=True)
class BlobFromImageConfig:
    shape: dict[str, int] = field(init=False)
    scale_factor: float
    mean_values: tuple[float, float, float]
    prototxt_path: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "shape", self._get_shape())
        mean_values = self.mean_values
        if isinstance(mean_values, str):
            mean_values = tuple(map(float, mean_values.split(", ")))
        object.__setattr__(self, "mean_values", mean_values)

    def _get_shape(self) -> dict[str, int]:
        pattern = r"input_shape\s*\{\s*dim:\s*(\d+)\s*dim:\s*(\d+)\s*dim:\s*(\d+)\s*dim:\s*(\d+)\s*\}"
        with open(self.prototxt_path, "r") as file:
            if match := re.search(pattern, file.read()):
                return {
                    "batch_size": int(match.group(1)),
                    "channels": int(match.group(2)),
                    "height": int(match.group(3)),
                    "width": int(match.group(4)),
                }
            else:
                raise ValidationError("Could not find input_shape in prototxt file.")


class ImageProcessor:
    """
    A class to handle image processing tasks, including face detection and encoding.

    """

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, face_distance_threshold: float) -> None:
        """
        Initialize the ImageProcessor with the required configurations.
        """
        self.storages = StorageManager()
        self.net = DNNInferenceManager(self.storages.get_storage("cv2")).get_model()

        self.blob_from_image_cfg = BlobFromImageConfig(
            scale_factor=config.BLOB_FROM_IMAGE_SCALE_FACTOR,
            mean_values=config.BLOB_FROM_IMAGE_MEAN_VALUES,
            prototxt_path=self.storages.get_storage("cv2").path(
                settings.DNN_FILES.get("prototxt").get("filename")
            ),
        )
        self.face_encodings_cfg = FaceEncodingsConfig(
            num_jitters=config.FACE_ENCODINGS_NUM_JITTERS,
            model=config.FACE_ENCODINGS_MODEL,
        )
        self.face_detection_confidence: float = config.FACE_DETECTION_CONFIDENCE
        self.distance_threshold: float = face_distance_threshold
        self.nms_threshold: float = config.NMS_THRESHOLD

    def _get_face_detections_dnn(
        self, filename: str
    ) -> list[tuple[int, int, int, int]]:
        """
        Detect faces in an image using the DNN model.

        Args:
            filename (str): The filename of the image to process.

        Returns:
            list[tuple[int, int, int, int]]: A list of tuples representing face regions in the image.
        """
        face_regions: list[tuple[int, int, int, int]] = []
        try:
            with self.storages.get_storage("images").open(filename, "rb") as img_file:
                img_array = np.frombuffer(img_file.read(), dtype=np.uint8)
                # Decode image from binary buffer to 3D numpy array (height, width, channels of BlueGreeRed color space)
                image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            (h, w) = image.shape[:2]
            # Create a blob (4D tensor) from the image
            blob = cv2.dnn.blobFromImage(
                image=cv2.resize(
                    image,
                    dsize=(
                        self.blob_from_image_cfg.shape["height"],
                        self.blob_from_image_cfg.shape["width"],
                    ),
                ),
                size=(
                    self.blob_from_image_cfg.shape["height"],
                    self.blob_from_image_cfg.shape["width"],
                ),
                scalefactor=self.blob_from_image_cfg.scale_factor,
                mean=self.blob_from_image_cfg.mean_values,
            )
            self.net.setInput(blob)
            # Forward pass to get output with shape (1, 1, N, 7),
            # where N is the number of faces and 7 are the detection values:
            # 1st: image index (0), 2nd: class label (0), 3rd: confidence (0-1),
            # 4th-5th: x, y coordinates, 6th-7th: width, height
            detections = self.net.forward()
            boxes, confidences = [], []
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                # Filter out weak detections by ensuring the confidence is greater than the minimum confidence
                if confidence > self.face_detection_confidence:
                    box = (detections[0, 0, i, 3:7] * np.array([w, h, w, h])).astype(
                        "int"
                    )
                    boxes.append(box)
                    confidences.append(confidence)
            if boxes:
                # Apply non-maxima suppression to suppress weak, overlapping bounding boxes
                indices = cv2.dnn.NMSBoxes(
                    boxes,
                    confidences,
                    self.face_detection_confidence,
                    self.nms_threshold,
                )
                if indices is not None:
                    for i in indices:
                        face_regions.append(tuple(boxes[i]))
        except Exception as e:
            self.logger.exception(
                "Error processing face detection for image %s", filename
            )
            raise e
        return face_regions

    def encode_face(self, filename: str, encodings_filename: str) -> None:
        """
        Encode faces detected in an image and save the encodings to storage.

        Args:
            filename (str): The filename of the image to process.
            encodings_filename (str): The filename to save the face encodings.
        """
        try:
            with self.storages.get_storage("images").open(filename, "rb") as img_file:
                image = face_recognition.load_image_file(img_file)
            encodings: list[np.ndarray[np.float32, Any]] = []
            face_regions = self._get_face_detections_dnn(filename)
            if not face_regions:
                self.logger.warning("No face regions detected in image %s", filename)
            else:
                for region in face_regions:
                    if isinstance(region, (list, tuple)) and len(region) == 4:
                        top, right, bottom, left = region
                        face_encodings = face_recognition.face_encodings(
                            image,
                            [(top, right, bottom, left)],
                            num_jitters=self.face_encodings_cfg.num_jitters,
                            model=self.face_encodings_cfg.model,
                        )
                        encodings.extend(face_encodings)
                    else:
                        self.logger.error("Invalid face region %s", region)
                        return
                with self.storages.get_storage("encoded").open(
                    encodings_filename, "wb"
                ) as f:
                    np.save(f, encodings)
        except Exception as e:
            self.logger.exception(
                "Error processing face encodings for image %s", filename
            )
            raise e
