import logging
import os
from typing import Any

import face_recognition
import numpy as np
from constance import config

from hope_dedup_engine.apps.faces.managers.storage import StorageManager
from hope_dedup_engine.apps.faces.services.image_processor import ImageProcessor
from hope_dedup_engine.apps.faces.validators import IgnorePairsValidator


class DuplicationDetector:
    """
    A class to detect and process duplicate faces in images.
    """

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(
        self, filenames: tuple[str], ignore_pairs: tuple[tuple[str, str], ...] = tuple()
    ) -> None:
        """
        Initialize the DuplicationDetector with the given filenames and ignore pairs.

        Args:
            filenames (tuple[str]): The filenames of the images to process.
            ignore_pairs (tuple[tuple[str, str]], optional):
                The pairs of filenames to ignore. Defaults to an empty tuple.
        """
        self.filenames = filenames
        self.ignore_set = IgnorePairsValidator.validate(ignore_pairs)
        self.storages = StorageManager()
        self.image_processor = ImageProcessor()

    def _encodings_filename(self, filename: str) -> str:
        """
        Generate the filename for the face encodings of a given image.

        Args:
            filename (str): The filename of the image.

        Returns:
            str: The filename for the face encodings.
        """
        return f"{filename}.npy"

    def _has_encodings(self, filename: str) -> bool:
        """
        Check if the face encodings for a given image exist in storage.

        Args:
            filename (str): The filename of the image.

        Returns:
            bool: True if the encodings exist, False otherwise.
        """
        return self.storages.get_storage("encoded").exists(
            self._encodings_filename(filename)
        )

    def _load_encodings_all(self) -> dict[str, list[np.ndarray[np.float32, Any]]]:
        """
        Load all face encodings from storage.

        Returns:
            dict[str, list[np.ndarray]]: A dictionary with filenames as keys and lists of face encodings as values.
        """
        data: dict[str, list[np.ndarray[np.float32, Any]]] = {}
        try:
            _, files = self.storages.get_storage("encoded").listdir("")
            for file in files:
                filename = os.path.splitext(file)[0]
                if file == self._encodings_filename(filename):
                    with self.storages.get_storage("encoded").open(file, "rb") as f:
                        data[filename] = np.load(f, allow_pickle=False)
        except Exception as e:
            self.logger.exception("Error loading encodings.")
            raise e
        return data

    @property
    def _existed_images_name(self) -> list[str]:
        """
        Return filenames from `self.filenames` that exist in the image storage, ensuring they have encodings.

        Returns:
            list[str]: List of existing filenames with encodings.
        """
        filenames: list = []
        _, files = self.storages.get_storage("images").listdir("")
        for filename in self.filenames:
            if filename not in files:
                self.logger.warning(
                    "Image %s not found in the image storage.", filename
                )
            else:
                filenames.append(filename)
                if not self._has_encodings(filename):
                    self.image_processor.encode_face(
                        filename, self._encodings_filename(filename)
                    )
        return filenames

    def find_duplicates(self) -> list[list[str]]:
        """
        Find and return a list of duplicate images based on face encodings.

        Returns:
            list[list[str]]: A list of lists, where each inner list contains
                                        the filenames of duplicate images.
        """
        try:
            duplicates: list[list[str]] = []
            encodings_all = self._load_encodings_all()
            for path1 in self._existed_images_name:
                duplicate: list[str] = [path1]
                encodings1 = encodings_all.get(path1)
                for path2, encodings2 in encodings_all.items():
                    if all(
                        (
                            path1 < path2,
                            (path1, path2) not in self.ignore_set,
                        )
                    ):
                        min_distance = config.FACE_DISTANCE_THRESHOLD
                        for encoding1 in encodings1:
                            if (
                                current_min := min(
                                    face_recognition.face_distance(
                                        encodings2, encoding1
                                    )
                                )
                            ) < min_distance:
                                min_distance = current_min
                        if min_distance < config.FACE_DISTANCE_THRESHOLD:
                            duplicate.append(path2)
                if len(duplicate) > 1:
                    duplicates.append(duplicate)
            return duplicates
        except Exception as e:
            self.logger.exception(
                "Error finding duplicates for images %s", self.filenames
            )
            raise e
