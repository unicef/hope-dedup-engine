import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass

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

    @dataclass(frozen=True, slots=True)
    class BlobFromImageConfig:
        shape: dict[str, int]
        scale_factor: float
        mean_values: tuple[float, float, float]

    @dataclass(frozen=True, slots=True)
    class FaceEncodingsConfig:
        num_jitters: int
        model: str

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, filenames: tuple[str], ignore_pairs: tuple[str, str] = tuple()) -> None:
        """
        Initialize the DuplicationDetector with the given filenames.

        Args:
            filenames (list[str]): The filenames of the images to process.
            ignore_pairs (list[tuple[str, str]]): The pairs of filenames to ignore.
        """
        self.storages: dict[str, CV2DNNStorage | HDEAzureStorage | HOPEAzureStorage] = {
            "images": HOPEAzureStorage(),
            "cv2dnn": CV2DNNStorage(settings.CV2DNN_PATH),
            "encoded": HDEAzureStorage(),
        }

        for file in (settings.PROTOTXT_FILE, settings.CAFFEMODEL_FILE):
            if not self.storages.get("cv2dnn").exists(file):
                raise FileNotFoundError(f"File {file} does not exist in storage.")

        self.net: cv2.dnn_Net = self._set_net(self.storages.get("cv2dnn"))

        self.filenames: tuple[str] = filenames
        self.ignore_set: set[tuple[str, str]] = self._get_pairs_to_ignore(ignore_pairs)

        self.blob_from_image_cfg = self.BlobFromImageConfig(
            shape=self._get_shape(),
            scale_factor=config.BLOB_FROM_IMAGE_SCALE_FACTOR,
            mean_values=(
                tuple(map(float, config.BLOB_FROM_IMAGE_MEAN_VALUES.split(", ")))
                if isinstance(config.BLOB_FROM_IMAGE_MEAN_VALUES, str)
                else config.BLOB_FROM_IMAGE_MEAN_VALUES
            ),
        )
        self.face_detection_confidence: float = config.FACE_DETECTION_CONFIDENCE
        self.distance_threshold: float = config.FACE_DISTANCE_THRESHOLD
        self.face_encodings_cfg = self.FaceEncodingsConfig(
            num_jitters=config.FACE_ENCODINGS_NUM_JITTERS,
            model=config.FACE_ENCODINGS_MODEL,
        )

        self.nms_threshold: float = config.NMS_THRESHOLD

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

    def _get_pairs_to_ignore(self, ignore: tuple[tuple[str, str]]) -> set[tuple[str, str]]:
        ignore = tuple(tuple(pair) for pair in ignore)
        if not ignore:
            return set()
        if all(
            isinstance(pair, tuple) and len(pair) == 2 and all(isinstance(item, str) and item for item in pair)
            for pair in ignore
        ):
            return {(item1, item2) for item1, item2 in ignore} | {(item2, item1) for item1, item2 in ignore}
        elif len(ignore) == 2 and all(isinstance(item, str) for item in ignore):
            return {(ignore[0], ignore[1]), (ignore[1], ignore[0])}
        else:
            raise ValueError(
                "Invalid format for 'ignore'. Expected tuple of tuples each containing exactly two strings."
            )

    def _encodings_filename(self, filename: str) -> str:
        return f"{filename}.npy"

    def _has_encodings(self, filename: str) -> bool:
        return self.storages["encoded"].exists(self._encodings_filename(filename))

    def _get_face_detections_dnn(self, filename: str) -> list[tuple[int, int, int, int]]:
        face_regions: list[tuple[int, int, int, int]] = []
        try:
            with self.storages["images"].open(filename, "rb") as img_file:
                img_array = np.frombuffer(img_file.read(), dtype=np.uint8)
                # Decode image from binary buffer to 3D numpy array (height, width, channels of BlueGreeRed color space)
                image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            (h, w) = image.shape[:2]
            # Create a blob (4D tensor) from the image
            blob = cv2.dnn.blobFromImage(
                image=cv2.resize(
                    image, dsize=(self.blob_from_image_cfg.shape["height"], self.blob_from_image_cfg.shape["width"])
                ),
                size=(self.blob_from_image_cfg.shape["height"], self.blob_from_image_cfg.shape["width"]),
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
            self.logger.exception("Error processing face detection for image %s", filename)
            raise e
        return face_regions

    def _load_encodings_all(self) -> dict[str, list[np.ndarray]]:
        data: dict[str, list[np.ndarray]] = {}
        try:
            _, files = self.storages["encoded"].listdir("")
            for file in files:
                if self._has_encodings(filename := os.path.splitext(file)[0]):
                    with self.storages["encoded"].open(file, "rb") as f:
                        data[filename] = np.load(f, allow_pickle=False)
        except Exception as e:
            self.logger.exception("Error loading encodings.")
            raise e
        return data

    def _encode_face(self, filename: str) -> None:
        try:
            with self.storages["images"].open(filename, "rb") as img_file:
                image = face_recognition.load_image_file(img_file)
            encodings: list = []
            face_regions = self._get_face_detections_dnn(filename)
            if not face_regions:
                self.logger.error("No face regions detected in image %s", filename)
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
                with self.storages["encoded"].open(self._encodings_filename(filename), "wb") as f:
                    np.save(f, encodings)
        except Exception as e:
            self.logger.exception("Error processing face encodings for image %s", filename)
            raise e

    def _get_duplicated_groups(self, checked: set[tuple[str, str, float]]) -> tuple[tuple[str]]:
        # Dictionary to store connections between paths where distances are less than the threshold
        groups = []
        connections = defaultdict(set)
        for path1, path2, dist in checked:
            if dist < self.distance_threshold:
                connections[path1].add(path2)
                connections[path2].add(path1)
        # Iterate over each path and form groups
        for path, neighbors in connections.items():
            # Check if the path has already been included in any group
            if not any(path in group for group in groups):
                new_group = {path}
                queue = list(neighbors)
                # Try to expand the group ensuring each new path is duplicated to all in the group
                while queue:
                    neighbor = queue.pop(0)
                    if neighbor not in new_group and all(neighbor in connections[member] for member in new_group):
                        new_group.add(neighbor)
                        # Add neighbors of the current neighbor, excluding those already in the group
                        queue.extend([n for n in connections[neighbor] if n not in new_group])
                # Add the newly formed group to the list of groups
                groups.append(new_group)
        return tuple(map(tuple, groups))

    def find_duplicates(self) -> tuple[tuple[str]]:
        """
        Find and return a list of duplicate images based on face encodings.

        Returns:
            tuple[tuple[str]]: A tuple of filenames of duplicate images.
        """
        try:
            for filename in self.filenames:
                if not self._has_encodings(filename):
                    self._encode_face(filename)
            encodings_all = self._load_encodings_all()

            checked = set()
            for path1, encodings1 in encodings_all.items():
                for path2, encodings2 in encodings_all.items():
                    if path1 < path2 and (path1, path2) not in self.ignore_set:
                        min_distance = float("inf")
                        for encoding1 in encodings1:
                            if (
                                current_min := min(face_recognition.face_distance(encodings2, encoding1))
                            ) < min_distance:
                                min_distance = current_min
                        checked.add((path1, path2, min_distance))

            return self._get_duplicated_groups(checked)
        except Exception as e:
            self.logger.exception("Error finding duplicates for images %s", self.filenames)
            raise e
