import logging
from typing import Generator
from uuid import UUID

import cv2
import numpy as np
from deepface import DeepFace

from hope_dedup_engine.apps.api.deduplication.config import ConfigDefaults
from hope_dedup_engine.apps.api.models import DeduplicationSet

# from hope_dedup_engine.apps.core.exceptions import NotCompliantImageError
from hope_dedup_engine.apps.faces.managers import StorageManager
from hope_dedup_engine.constants import FacialError, is_facial_error


class FacialDetector:

    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(
        self,
        deduplication_set_pk: UUID,
        filenames: tuple[str],
        options: ConfigDefaults,
        ignore_pairs: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self.deduplication_set = DeduplicationSet.objects.get(pk=deduplication_set_pk)
        print(f"{self.deduplication_set=}")
        self.filenames = filenames
        self.options = options
        # self.ignore_set = IgnorePairsValidator.validate(ignore_pairs)
        self.storages = StorageManager()

    def find_duplicates(
        self,
        # tracker: Callable[[int], None] | None = None
    ) -> Generator[tuple[str, str, float], None, None]:
        self.encode_faces()
        encodings = self.deduplication_set.get_encodings()
        for file1 in self.filenames:
            # if tracker:
            #     tracker(100 * n // len(self.filenames))
            enc1 = encodings.get(file1)
            if is_facial_error(enc1):
                yield (file1, FacialError[enc1].name, FacialError[enc1].code)
                continue
            for file2, enc2 in encodings.items():
                if file1 == file2:
                    continue
                if is_facial_error(enc2):
                    # yield (file2, FacialError[enc2].name, FacialError[enc2].code)
                    continue
                # TODO: use threshold
                verified = DeepFace.verify(enc1, enc2, **(self.options or {}))
                yield (file1, file2, verified.get("distance"))

    def encode_faces(self) -> None:
        encodings = {}
        _, images = self.storages.get_storage("images").listdir("")
        for file in self.filenames:
            if file not in images:
                encodings[file] = FacialError.NO_FILE_FOUND.name
                continue
            with self.storages.get_storage("images").open(file, "rb") as img_file:
                img_array = np.frombuffer(img_file.read(), dtype=np.uint8)
                img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                try:
                    dp_encodings = DeepFace.represent(img_bgr, **(self.options or {}))
                    if len(dp_encodings) > 1:
                        encodings[file] = FacialError.MULTIPLE_FACES_DETECTED.name
                    else:
                        encodings[file] = dp_encodings[0].get("embedding")
                except TypeError:
                    encodings[file] = FacialError.GENERIC_ERROR.name
                except ValueError:
                    encodings[file] = FacialError.NO_FACE_DETECTED.name
        self.deduplication_set.update_encodings(encodings)
