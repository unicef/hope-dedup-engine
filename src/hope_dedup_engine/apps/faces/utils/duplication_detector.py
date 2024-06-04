import logging
import os
import re

from django.conf import settings

import cv2
import face_recognition
import numpy as np
from constance import config

from hope_dedup_engine.apps.core.storage import CV2DNNStorage, HDEAzureStorage, HOPEAzureStorage


class DuplicationDetector:
    """
    A class to detect and process duplicate faces in images.
    """

    def __init__(self, filename: str) -> None:
        """
        Initialize the DuplicationDetector with the given filename.

        Args:
            filename (str): The filename of the image to process.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.storages: dict[str, CV2DNNStorage | HDEAzureStorage | HOPEAzureStorage] = {
            "images": HOPEAzureStorage(),
            "cv2dnn": CV2DNNStorage(settings.CV2DNN_PATH),
            "encoded": HDEAzureStorage(),
        }

        for file in (settings.PROTOTXT_FILE, settings.CAFFEMODEL_FILE):
            if not self.storages.get("cv2dnn").exists(file):
                raise FileNotFoundError(f"File {file} does not exist in storage.")

        self.shape: dict[str, int] = self._get_shape()
        self.net: cv2.dnn_Net = self._set_net(self.storages.get("cv2dnn"))

        self.filename: str = filename
        self.encodings_filename: str = f"{self.filename}.npy"
        self.scale_factor: float = config.BLOB_FROM_IMAGE_SCALE_FACTOR
        self.mean_values: tuple[float, float, float] = tuple(map(float, config.BLOB_FROM_IMAGE_MEAN_VALUES.split(", ")))
        # self.mean_values: config.BLOB_FROM_IMAGE_MEAN_VALUES
        self.face_detection_confidence: float = config.FACE_DETECTION_CONFIDENCE
        self.face_encodings_model: str = config.FACE_ENCODINGS_MODEL
        self.face_encodings_num_jitters: int = config.FACE_ENCODINGS_NUM_JITTERS
        self.distance_threshold: float = config.FACE_DISTANCE_THRESHOLD
        self.nms_threshold: float = config.NMS_THRESHOLD

    @property
    def has_encodings(self) -> bool:
        return self.storages["encoded"].exists(self.encodings_filename)

    def _set_net(self, storage: CV2DNNStorage) -> cv2.dnn_Net:
        net = cv2.dnn.readNetFromCaffe(
            storage.path(settings.PROTOTXT_FILE),
            storage.path(settings.CAFFEMODEL_FILE),
        )
        net.setPreferableBackend(int(config.DNN_BACKEND))
        net.setPreferableTarget(int(config.DNN_TARGET))
        return net

    def _get_shape(self) -> dict[str, int]:
        pattern = r"input_shape\s*\{\s*" r"dim:\s*(\d+)\s*" r"dim:\s*(\d+)\s*" r"dim:\s*(\d+)\s*" r"dim:\s*(\d+)\s*\}"
        with open(settings.PROTOTXT_FILE, "r") as file:
            if match := re.search(pattern, file.read()):
                return {
                    "batch_size": int(match.group(1)),
                    "channels": int(match.group(2)),
                    "height": int(match.group(3)),
                    "width": int(match.group(4)),
                }
            else:
                raise ValueError("Could not find input_shape in prototxt file.")

    def _get_face_detections_dnn(self) -> list[tuple[int, int, int, int]]:
        face_regions: list[tuple[int, int, int, int]] = []
        try:
            with self.storages["images"].open(self.filename, "rb") as img_file:
                img_array = np.frombuffer(img_file.read(), dtype=np.uint8)
                # Decode image from binary buffer to 3D numpy array (height, width, channels of BlueGreeRed color space)
                image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            (h, w) = image.shape[:2]
            # Create a blob (4D tensor) from the image
            blob = cv2.dnn.blobFromImage(
                image=cv2.resize(image, dsize=(self.shape["height"], self.shape["width"])),
                size=(self.shape["height"], self.shape["width"]),
                scalefactor=self.scale_factor,
                mean=self.mean_values,
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
                    box = (detections[0, 0, i, 3:7] * np.array([w, h, w, h])).astype("int")
                    boxes.append(box)
                    confidences.append(confidence)
            if boxes:
                # Apply non-maxima suppression to suppress weak, overlapping bounding boxes
                indices = cv2.dnn.NMSBoxes(boxes, confidences, self.face_detection_confidence, self.nms_threshold)
                if indices is not None:
                    for i in indices:
                        face_regions.append(tuple(boxes[i]))
        except Exception as e:
            self.logger.exception("Error processing face detection for image %s", self.filename)
            raise e
        return face_regions

    def _load_encodings_all(self) -> dict[str, list[np.ndarray]]:
        data: dict[str, list[np.ndarray]] = {}
        try:
            _, files = self.storages["encoded"].listdir("")
            for file in files:
                if file.endswith(".npy"):
                    with self.storages["encoded"].open(file, "rb") as f:
                        data[os.path.splitext(file)[0]] = np.load(f, allow_pickle=False)
        except Exception as e:
            self.logger.exception("Error loading encodings.")
            raise e
        return data

    def _encode_face(self) -> None:
        try:
            with self.storages["images"].open(self.filename, "rb") as img_file:
                image = face_recognition.load_image_file(img_file)
            encodings: list = []
            face_regions = self._get_face_detections_dnn()
            if not face_regions:
                self.logger.error("No face regions detected in image %s", self.filename)
            else:
                for region in face_regions:
                    if isinstance(region, (list, tuple)) and len(region) == 4:
                        top, right, bottom, left = region
                        # Compute the face encodings for the face regions in the image
                        face_encodings = face_recognition.face_encodings(
                            image,
                            [(top, right, bottom, left)],
                            num_jitters=self.face_encodings_num_jitters,
                            model=self.face_encodings_model,
                        )
                        encodings.extend(face_encodings)
                    else:
                        self.logger.error("Invalid face region.")
                with self.storages["encoded"].open(self.encodings_filename, "wb") as f:
                    np.save(f, encodings)
        except Exception as e:
            self.logger.exception("Error processing face encodings for image %s", self.filename)
            raise e

    def find_duplicates(self) -> tuple[str]:
        """
        Find and return a list of duplicate images based on face encodings.

        Returns:
            tuple[str]: A tuple of filenames of duplicate images.
        """
        duplicated_images: set[str] = set()
        path1 = self.filename
        try:
            if not self.has_encodings:
                self._encode_face()
            encodings_all = self._load_encodings_all()
            encodings1 = encodings_all[path1]

            checked_pairs = set()
            for path2, encodings2 in encodings_all.items():
                if path1 != path2:
                    for encoding1 in encodings1:
                        for encoding2 in encodings2:
                            if (path1, path2, tuple(encoding1), tuple(encoding2)) in checked_pairs:
                                continue

                            distance = face_recognition.face_distance([encoding1], encoding2)
                            if distance < self.distance_threshold:
                                duplicated_images.update([path1, path2])
                                break

                            checked_pairs.add((path1, path2, tuple(encoding1), tuple(encoding2)))
                        if path2 in duplicated_images:
                            break
            return tuple(duplicated_images)
        except Exception as e:
            self.logger.exception("Error finding duplicates for image %s", path1)
            raise e
