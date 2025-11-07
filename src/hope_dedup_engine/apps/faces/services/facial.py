import logging
from collections.abc import Iterable, Callable
from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from deepface import DeepFace

from hope_dedup_engine.apps.api.models import Image, Encoding
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager
from hope_dedup_engine.apps.faces.utils import is_facial_error, report_long_execution
from hope_dedup_engine.type_aliases import EncodingType, FindingType, IgnoredPairType

logger = logging.getLogger(__name__)


def default_progress(*args):
    return True


def encode_faces(
    files: list[str],
    process_encoding_error: Callable[[str, Image.StatusCode], None],
    options=None,
    pre_encodings=None,
) -> tuple[EncodingType, int, int]:
    with report_long_execution("ImagesStorageManager()"):
        storage = ImagesStorageManager()

    encoded = {}
    if pre_encodings:
        with report_long_execution("encoded.update(pre_encodings)"):
            encoded.update(pre_encodings)
    added_cnt = existing_cnt = 0
    for file in files:
        if file in encoded:
            existing_cnt += 1
            continue
        try:
            with report_long_execution("DeepFace.represent(storage.load_image(file), **(options or {}))"):
                result = DeepFace.represent(
                    storage.load_image(file), max_faces=2, enforce_detection=False, **(options or {})
                )
            if len(result) > 1:
                encoded[file] = Image.StatusCode.MULTIPLE_FACES_DETECTED.value
                process_encoding_error(file, Image.StatusCode.MULTIPLE_FACES_DETECTED)
            elif result[0]["face_confidence"] == 0.0:
                encoded[file] = Image.StatusCode.NO_FACE_DETECTED.value
                process_encoding_error(file, Image.StatusCode.NO_FACE_DETECTED)
            else:
                encoded[file] = result[0]["embedding"]
                added_cnt += 1
        except TypeError as e:
            logger.exception(e)
            encoded[file] = Image.StatusCode.GENERIC_ERROR.value
            process_encoding_error(file, Image.StatusCode.GENERIC_ERROR)
        except ResourceNotFoundError:
            encoded[file] = Image.StatusCode.NO_FILE_FOUND.value
            process_encoding_error(file, Image.StatusCode.NO_FILE_FOUND)

    return encoded, added_cnt, existing_cnt


def dedupe_images(  # noqa 901
    encoding_pairs: Iterable[tuple[Encoding, Encoding]],
    ignored_pairs: IgnoredPairType,
    dedupe_threshold: float,
    options: dict[str, Any] | None = None,
) -> FindingType:
    config = options or {}
    results: FindingType = []

    for encoding0, encoding1 in encoding_pairs:
        if is_facial_error(encoding0.status_code) or is_facial_error(encoding1.status_code):
            continue

        if (encoding0.filename, encoding1.filename) in ignored_pairs or (
            encoding1.filename,
            encoding0.filename,
        ) in ignored_pairs:
            continue

        res = DeepFace.verify(encoding0.embedding, encoding1.embedding, **config)
        similarity = float(1 - res["distance"])
        if similarity >= dedupe_threshold:
            results.append(
                (encoding0.filename, encoding1.filename, similarity, Image.StatusCode.DEDUPLICATE_SUCCESS.value)
            )

    return results
