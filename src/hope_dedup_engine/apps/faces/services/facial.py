import logging
import os
from collections.abc import Callable
from itertools import combinations
from typing import Any, Generator

import cv2
import numpy as np
from constance import config
from deepface import DeepFace

from hope_dedup_engine.apps.api.deduplication.config import ConfigDefaults
from hope_dedup_engine.apps.core.exceptions import NotCompliantImageError
from hope_dedup_engine.apps.faces.managers import StorageManager


class FacialDetector:

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(
        self,
        filenames: tuple[str],
        options: ConfigDefaults,
        ignore_pairs: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self.filenames = filenames
        self.options = options
        # self.ignore_set = IgnorePairsValidator.validate(ignore_pairs)
        self.storages = StorageManager()

    def _encodings_filename(self, filename: str) -> str:
        return f"{filename}.npy"

    def _has_encodings(self, filename: str) -> bool:
        return self.storages.get_storage("encoded").exists(
            self._encodings_filename(filename)
        )

    def _load_encodings_all(self) -> dict[str, list[np.ndarray[np.float32, Any]]]:
        data: dict[str, list[np.ndarray[np.float32, Any]]] = {}
        try:
            _, files = self.storages.get_storage("encoded").listdir("")
            for file in files:
                filename = os.path.splitext(file)[0]
                if file == self._encodings_filename(filename):
                    with self.storages.get_storage("encoded").open(file, "rb") as f:
                        data[filename] = list(np.load(f, allow_pickle=False))
        except Exception as e:
            self.logger.exception("Error loading encodings.")
            raise e
        return data

    def _existed_images_name(self) -> list[str]:
        filenames: list = []
        _, files = self.storages.get_storage("images").listdir("")
        print(f"\n{'='*100}\n{files=}\n{'='*100}\n")
        for filename in self.filenames:
            if filename not in files:
                self.logger.warning(
                    "Image %s not found in the image storage.", filename
                )
            else:
                filenames.append(filename)
                if not self._has_encodings(filename):
                    self.encode_face(filename, self._encodings_filename(filename))
        return filenames

    def find_duplicates(
        self, tracker: Callable[[int], None] | None = None
    ) -> Generator[tuple[str, str, float], None, None]:
        try:
            existed_images_name = self._existed_images_name()
            encodings_all = self._load_encodings_all()
            self.options = {**self.options, "threshold": config.FACE_DISTANCE_THRESHOLD}
            total_pairs = (n := len(existed_images_name)) * (n - 1) // 2
            for i, (path1, path2) in enumerate(combinations(existed_images_name, 2), 1):
                encodings1 = encodings_all.get(path1)
                encodings2 = encodings_all.get(path2)
                if encodings1 is None or encodings2 is None:
                    continue
                verified = DeepFace.verify(
                    encodings1, encodings2, **(self.options or {})
                )
                yield (path1, path2, verified.get("distance"))

                if tracker:
                    tracker(100 * i // total_pairs)

        except Exception as e:
            self.logger.exception(
                "Error finding duplicates for images %s", self.filenames
            )
            raise e

    def encode_face(self, filename: str, encodings_filename: str) -> None:
        try:
            with self.storages.get_storage("images").open(filename, "rb") as img_file:
                img_array = np.frombuffer(img_file.read(), dtype=np.uint8)
                img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                face_regions = DeepFace.represent(img_bgr, **(self.options or {}))
                if not face_regions:
                    raise NotCompliantImageError(
                        f"No face regions detected in image '{filename}'."
                    )
                if len(face_regions) > 1:
                    raise NotCompliantImageError(
                        f"Multiple face regions detected in image '{filename}'."
                    )
                else:
                    with self.storages.get_storage("encoded").open(
                        encodings_filename, "wb"
                    ) as f:
                        np.save(f, face_regions[0].get("embedding"))
        except Exception as e:
            self.logger.exception(
                "Error processing face encodings for image %s", filename
            )
            raise e
