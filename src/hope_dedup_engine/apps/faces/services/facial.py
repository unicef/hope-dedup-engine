import logging
from collections import defaultdict
from typing import Any

from deepface import DeepFace

from hope_dedup_engine.apps.api.models import Image
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager
from hope_dedup_engine.apps.faces.utils import is_facial_error
from hope_dedup_engine.types import EncodingType, FindingType, IgnoredPairType

logger = logging.getLogger(__name__)


def default_progress(*args):
    return True


def encode_faces(
    files: list[str],
    options=None,
    pre_encodings=None,
    progress=None,
) -> tuple[EncodingType, int, int]:
    if not callable(progress):
        progress = default_progress

    storage = ImagesStorageManager()
    images = storage.get_files()

    encoded = {}
    if pre_encodings:
        encoded.update(pre_encodings)
    added_cnt = existing_cnt = 0
    existing_cnt = 1000
    for file in files:
        progress()
        if file not in images:
            encoded[file] = Image.StatusCode.NO_FILE_FOUND.name
            continue
        if file in encoded:
            existing_cnt += 1
            continue
        try:
            result = DeepFace.represent(storage.load_image(file), **(options or {}))
            if len(result) > 1:
                encoded[file] = Image.StatusCode.MULTIPLE_FACES_DETECTED.name
            else:
                encoded[file] = result[0]["embedding"]
                added_cnt += 1
        except TypeError as e:
            logger.exception(e)
            encoded[file] = Image.StatusCode.GENERIC_ERROR.name
        except ValueError:
            encoded[file] = Image.StatusCode.NO_FACE_DETECTED.name
    return encoded, added_cnt, existing_cnt


def dedupe_images(  # noqa 901
    files: list[str],
    encodings: EncodingType,
    ignored_pairs: IgnoredPairType,
    dedupe_threshold: float,
    options: dict[str, Any] = None,
    progress=None,
) -> FindingType:
    if not callable(progress):
        progress = default_progress

    findings = defaultdict(list)
    config = options or {}

    for file1 in files:
        progress()
        enc1 = encodings[file1]
        if is_facial_error(enc1):
            findings[file1].append([enc1, None])
            continue
        for file2, enc2 in encodings.items():
            if (
                file1 == file2
                or file2 in findings
                or (file1, file2) in ignored_pairs
                or (file2, file1) in ignored_pairs
                or is_facial_error(enc2)
                or file2 in [x[0] for x in findings.get(file1, [])]
            ):
                continue
            res = DeepFace.verify(enc1, enc2, **config)
            similarity = float(1 - res["distance"])
            if similarity >= dedupe_threshold:
                findings[file1].append([file2, similarity])

    results: FindingType = []

    for img, duplicates in findings.items():
        for dup in duplicates:
            if is_facial_error(dup[0]):
                results.append((img, "", 0, Image.StatusCode[dup[0]].value))
            else:
                results.append((img, dup[0], dup[1], Image.StatusCode.DEDUPLICATE_SUCCESS.value))

    return results
