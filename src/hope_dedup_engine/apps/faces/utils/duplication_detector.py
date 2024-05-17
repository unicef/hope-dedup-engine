import logging
import os
import pickle
from typing import Dict, List, Tuple

from django.conf import settings

import cv2
import face_recognition
import numpy as np

from hope_dedup_engine.apps.core.storage import CV2DNNStorage, HDEAzureStorage, HOPEAzureStorage


class DuplicationDetector:
    def __init__(self, filename: str) -> None:
        self.logger = logging.getLogger(__name__)

        self.storages = {
            "images": HOPEAzureStorage(),
            "cv2dnn": CV2DNNStorage(),
            "encoded": HDEAzureStorage(),
        }

        self.filename: str = filename
        self.encodings_filename = f"{self.filename}.pkl"

        self.confidence: float = settings.FACE_DETECTION_CONFIDENCE
        self.threshold: float = settings.DISTANCE_THRESHOLD

        for file in (settings.PROTOTXT_FILE, settings.CAFFEMODEL_FILE):
            if not self.storages.get("cv2dnn").exists(file):
                raise FileNotFoundError(f"File {file} does not exist in storage.")

        self.net = cv2.dnn.readNetFromCaffe(
            self.storages.get("cv2dnn").path(settings.PROTOTXT_FILE),
            self.storages.get("cv2dnn").path(settings.CAFFEMODEL_FILE),
        )

        self.net.setPreferableBackend(settings.DNN_BACKEND)
        self.net.setPreferableTarget(settings.DNN_TARGET)

    @property
    def has_encodings(self) -> bool:
        return self.storages["encoded"].exists(self.encodings_filename)

    def _get_face_detections_dnn(self) -> List[Tuple[int, int, int, int]]:
        # TODO: Implement case if face regions for image are not detected
        face_regions: List[Tuple[int, int, int, int]] = []
        try:
            with self.storages["images"].open(self.filename, "rb") as img_file:
                img_array = np.frombuffer(img_file.read(), dtype=np.uint8)
                image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            (h, w) = image.shape[:2]
            blob = cv2.dnn.blobFromImage(
                image=cv2.resize(image, dsize=(300, 300)), scalefactor=1.0, size=(300, 300), mean=(104.0, 177.0, 123.0)
            )
            self.net.setInput(blob)
            detections = self.net.forward()
            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > self.confidence:
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    face_regions.append(tuple(box.astype("int").tolist()))
        except Exception as e:
            self.logger.exception(f"Error processing face detection for image {self.filename}", exc_info=e)
        return face_regions

    def _load_encodings_all(self) -> Dict[str, List[np.ndarray]]:
        data: Dict[str, List[np.ndarray]] = {}
        try:
            _, files = self.storages["encoded"].listdir("")
            for file in files:
                if file.endswith(".pkl"):
                    with self.storages["encoded"].open(file, "rb") as f:
                        data[os.path.splitext(file)[0]] = pickle.load(f)
        except Exception as e:
            self.logger.exception(f"Error loading encodings: {e}", exc_info=True)
        return data

    def _encode_face(self) -> None:
        try:
            with self.storages["images"].open(self.filename, "rb") as img_file:
                image = face_recognition.load_image_file(img_file)
            encodings: list = []
            face_regions = self._get_face_detections_dnn()
            for region in face_regions:
                if isinstance(region, (list, tuple)) and len(region) == 4:
                    top, right, bottom, left = region
                    face_encodings = face_recognition.face_encodings(image, [(top, right, bottom, left)], model="hog")
                    encodings.extend(face_encodings)
                else:
                    self.logger.error(f"Invalid face region {region}")
            with self.storages["encoded"].open(self.encodings_filename, "wb") as f:
                pickle.dump(encodings, f)
        except Exception as e:
            self.logger.exception(f"Error processing face encodings for image {self.filename}", exc_info=e)

    def find_duplicates(self) -> Tuple[str]:
        duplicated_images = set()
        path1 = self.filename
        try:
            if not self.has_encodings:
                self._encode_face()
            encodings_all = self._load_encodings_all()
            encodings1 = encodings_all[path1]

            for path2, encodings2 in encodings_all.items():
                if path1 != path2:
                    for encoding1 in encodings1:
                        for encoding2 in encodings2:
                            distance = face_recognition.face_distance([encoding1], encoding2)
                            print(f"{distance.item():10.8f}\t{path1} vs {path2}")
                            if distance < settings.DISTANCE_THRESHOLD:
                                duplicated_images.update([path1, path2])
                                break
                        if path2 in duplicated_images:
                            break
            return tuple(duplicated_images)
        except Exception as e:
            self.logger.exception(f"Error finding duplicates for image {path1}", exc_info=e)
            return tuple(duplicated_images)
