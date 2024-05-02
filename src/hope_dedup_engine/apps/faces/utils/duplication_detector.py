import logging
from pathlib import PosixPath
from typing import List, Tuple

from django.conf import settings

import cv2
import face_recognition
import numpy as np


class DuplicationDetector:
    def __init__(self, image_path: PosixPath) -> None:
        self.logger = logging.getLogger(__name__)
        self.net = cv2.dnn.readNetFromCaffe(
            str(settings.PROTOTXT_FILE),
            str(settings.CAFFEMODEL_FILE),
        )
        self.net.setPreferableBackend(settings.DNN_BACKEND)
        self.net.setPreferableTarget(settings.DNN_TARGET)
        self.threshold = settings.DISTANCE_THRESHOLD
        self.image_path = image_path

    @property
    def has_encodings(self) -> bool:
        return bool(settings.ENCODED_PATH / self.image_path.name)

    def _get_face_detections_dnn(self) -> List[Tuple[int, int, int, int]]:
        try:
            image: np.ndarray = cv2.imread(str(self.image_path))
            (h, w) = image.shape[:2]
            blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
            self.net.setInput(blob)
            detections = self.net.forward()
            face_regions: List[Tuple[int, int, int, int]] = []
            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.5:
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    face_regions.append(box.astype("int").tolist())
            return face_regions
        except Exception as e:
            self.logger.exception(f"Error processing image {str(self.image_path)}", exc_info=e)
            raise e

    def encode_faces(self) -> list:
        image = face_recognition.load_image_file(self.image_path)
        encodings: list = []
        face_regions = self._get_face_detections_dnn()
        for region in face_regions:
            if isinstance(region, (list, tuple)) and len(region) == 4:
                top, right, bottom, left = region
                face_encodings = face_recognition.face_encodings(image, [(top, right, bottom, left)], model="hog")
                encodings.extend(face_encodings)
            else:
                self.logger.error(f"Invalid face region {region}")
        return encodings

    def deduplicate(self):
        raise NotImplementedError("deduplicate not implemented yet")
