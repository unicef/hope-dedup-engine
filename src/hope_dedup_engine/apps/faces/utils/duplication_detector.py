import logging
import pickle
from typing import List, Tuple

from django.conf import settings

import cv2
import face_recognition
import numpy as np


class DuplicationDetector:
    def __init__(self, filename: str) -> None:
        self.logger = logging.getLogger(__name__)
        self.net = cv2.dnn.readNetFromCaffe(
            str(settings.PROTOTXT_FILE),
            str(settings.CAFFEMODEL_FILE),
        )
        self.net.setPreferableBackend(settings.DNN_BACKEND)
        self.net.setPreferableTarget(settings.DNN_TARGET)
        self.threshold: float = settings.DISTANCE_THRESHOLD
        self.filename: str = filename
        self.encodings_file = settings.ENCODED_PATH / f"{self.filename}.pkl"

    @property
    def has_encodings(self) -> bool:
        return bool(self.encodings_file.exists())

    def _get_face_detections_dnn(self) -> List[Tuple[int, int, int, int]]:
        # TODO: Implement case if face regions for image are not detected
        try:
            image: np.ndarray = cv2.imread(str(settings.IMAGES_PATH / f"{self.filename}"))
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
            self.logger.exception(f"Error processing face detection for image {self.filename}", exc_info=e)

    def _load_encodings(self):
        data: dict = {}
        try:
            for file in settings.ENCODED_PATH.iterdir():
                if file.is_file() and file.suffix == ".pkl":
                    with file.open("rb") as f:
                        data[file.stem] = pickle.load(f)
            return data
        except Exception as e:
            self.logger.exception(f"Error loading encodings for image {self.filename}", exc_info=e)

    def encode_faces(self) -> None:
        try:
            image = face_recognition.load_image_file(settings.IMAGES_PATH / self.filename)
            encodings: list = []
            face_regions = self._get_face_detections_dnn()
            for region in face_regions:
                if isinstance(region, (list, tuple)) and len(region) == 4:
                    top, right, bottom, left = region
                    face_encodings = face_recognition.face_encodings(image, [(top, right, bottom, left)], model="hog")
                    encodings.extend(face_encodings)
                else:
                    self.logger.error(f"Invalid face region {region}")
            with open(self.encodings_file, "wb") as f:
                pickle.dump(encodings, f)
            return
        except Exception as e:
            self.logger.exception(f"Error processing face encodings for image {self.filename}", exc_info=e)

    def find_duplicates(self) -> Tuple[str]:
        duplicated_images = set()
        try:
            encodings_all = self._load_encodings()
            path1 = self.filename
            if path1 not in encodings_all:
                self.logger.error(f"Encodings for {path1} not found.")
                return tuple(duplicated_images)

            encodings1 = encodings_all[path1]
            for path2, encodings2 in encodings_all.items():
                if path1 != path2:
                    for encoding1 in encodings1:
                        for encoding2 in encodings2:
                            distance = face_recognition.face_distance([encoding1], encoding2)
                            self.logger.info(f"{distance.item():10.8f}\t{path1} vs {path2}")
                            if distance < settings.DISTANCE_THRESHOLD:
                                duplicated_images.update([path1, path2])
                                break
                        if path2 in duplicated_images:
                            break
            return tuple(duplicated_images)
        except Exception as e:
            self.logger.exception(f"Error finding duplicates for image {path1}", exc_info=e)
            return tuple(duplicated_images)

    def find_all_duplicates(self) -> Tuple[str]:
        duplicated_images = set()
        checked_images = set()
        try:
            encodings_all = self._load_encodings()
            for path1, encodings1 in encodings_all.items():
                if path1 in checked_images:
                    continue
                for path2, encodings2 in encodings_all.items():
                    if path1 != path2 and path2 not in checked_images:
                        for encoding1 in encodings1:
                            for encoding2 in encodings2:
                                distance = face_recognition.face_distance([encoding1], encoding2)
                                logging.info(f"{distance.item():10.8f}\t{path1} vs {path2}")
                                if distance < settings.DISTANCE_THRESHOLD:
                                    duplicated_images.update([path1, path2])
                                    break
                            if path2 in duplicated_images:
                                break
                checked_images.add(path1)
            return tuple(duplicated_images)
        except Exception as e:
            self.logger.exception("Error finding duplicates", exc_info=e)
