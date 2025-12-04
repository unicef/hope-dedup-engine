import logging
from collections import defaultdict
from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from deepface import DeepFace
from hope_dedup_engine.apps.api.models import Image
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager
from hope_dedup_engine.apps.faces.utils import is_facial_error, report_long_execution
from hope_dedup_engine.type_aliases import EncodingType, FindingType, IgnoredPairType

logger = logging.getLogger(__name__)


def default_progress(*args):
    return True


def encode_faces(  # noqa 901
    files: list[str],
    config: dict[str, Any] | None = None,
    pre_encodings=None,
    progress=None,
) -> tuple[EncodingType, int, int]:
    if not callable(progress):
        progress = default_progress

    with report_long_execution("ImagesStorageManager()"):
        storage = ImagesStorageManager()

    encoded = {}
    if pre_encodings:
        with report_long_execution("encoded.update(pre_encodings)"):
            encoded.update(pre_encodings)
    added_cnt = existing_cnt = 0
    existing_cnt = 1000

    options = config.get("encoding") if config else {}
    confidence_threshold = config.get("face_confidence_threshold") if config else None

    for file in files:
        with report_long_execution("progress()"):
            progress()
        if file in encoded:
            existing_cnt += 1
            continue
        try:
            with report_long_execution("DeepFace.represent(storage.load_image(file), **(options or {}))"):
                result = DeepFace.represent(storage.load_image(file), **(options or {}))

            if not result:
                encoded[file] = Image.StatusCode.NO_FACE_DETECTED.value
                continue
            if len(result) > 1:
                encoded[file] = Image.StatusCode.MULTIPLE_FACES_DETECTED.value
                continue

            face_obj = result[0]
            if confidence_threshold is not None:
                face_confidence = face_obj.get("face_confidence")
                if isinstance(face_confidence, (int | float)) and face_confidence < confidence_threshold:
                    encoded[file] = Image.StatusCode.NO_FACE_ACCEPTED.value
                    continue

            encoded[file] = face_obj["embedding"]
            added_cnt += 1

        except TypeError as e:
            logger.exception(e)
            encoded[file] = Image.StatusCode.GENERIC_ERROR.value
        except ValueError:
            encoded[file] = Image.StatusCode.NO_FACE_DETECTED.value
        except ResourceNotFoundError:
            encoded[file] = Image.StatusCode.NO_FILE_FOUND.value

    return encoded, added_cnt, existing_cnt


def dedupe_images(  # noqa 901
    files0: list[str],
    files1: list[str],
    encodings: EncodingType,
    ignored_pairs: IgnoredPairType,
    config: dict[str, Any] | None = None,
    progress=None,
) -> FindingType:
    if not callable(progress):
        progress = default_progress

    findings = defaultdict(list)
    options = config.get("deduplicate") if config else {}

    for i, file1 in enumerate(files0):
        progress()
        enc1 = encodings[file1]
        if is_facial_error(enc1):
            findings[file1].append([enc1, None])
            continue

        if files0 == files1:
            files1_ = files1[i + 1 :]
        else:
            files1_ = files1

        for file2 in files1_:
            enc2 = encodings[file2]
            if (
                file2 in findings
                or (file1, file2) in ignored_pairs
                or (file2, file1) in ignored_pairs
                or is_facial_error(enc2)
                or any(file2 == dup[0] for dup in findings.get(file1, []))
            ):
                continue
            res = DeepFace.verify(enc1, enc2, **options)
            confidence = res.get("confidence", 0)
            if confidence >= config.get("duplicate_confidence_threshold", 0):
                findings[file1].append([file2, confidence / 100])

    results: FindingType = []

    for img, duplicates in findings.items():
        for dup in duplicates:
            if is_facial_error(dup[0]):
                results.append((img, "", 0, Image.StatusCode(dup[0]).value))
            else:
                results.append((img, dup[0], dup[1], Image.StatusCode.DEDUPLICATE_SUCCESS.value))

    return results
