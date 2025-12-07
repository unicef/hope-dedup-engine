import logging
from collections.abc import Callable
from collections import defaultdict
from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from deepface import DeepFace
from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager
from hope_dedup_engine.apps.faces.utils import is_facial_error, report_long_execution
from hope_dedup_engine.type_aliases import EncodingType, FindingType, IgnoredPairType

logger = logging.getLogger(__name__)


def encode_faces(  # noqa 901
    files: list[str],
    process_encoding_error: Callable[[str, Encoding.StatusCode], None],
    config: dict[str, Any] | None = None,
    pre_encodings=None,
) -> tuple[EncodingType, int, int]:
    with report_long_execution("ImagesStorageManager()"):
        storage = ImagesStorageManager()

    encoded = {}
    if pre_encodings:
        with report_long_execution("encoded.update(pre_encodings)"):
            encoded.update(pre_encodings)
    added_cnt = existing_cnt = 0

    options = config.get("encoding") if config else {}

    for file in files:
        if file in encoded:
            existing_cnt += 1
            continue
        try:
            with report_long_execution("DeepFace.represent(storage.load_image(file), **(options or {}))"):
                result = DeepFace.represent(storage.load_image(file), **(options or {}))

            face_confidence = float(result[0]["face_confidence"])
            threshold = config.get("face_confidence_threshold", 0.0) if config else 0.0
            match (len(result), face_confidence):
                case (l, _) if l > 1:
                    encoded[file] = Encoding.StatusCode.MULTIPLE_FACES_DETECTED.value
                    process_encoding_error(file, Encoding.StatusCode.MULTIPLE_FACES_DETECTED)

                case (_, fc) if fc == 0.0:
                    encoded[file] = Encoding.StatusCode.NO_FACE_DETECTED.value
                    process_encoding_error(file, Encoding.StatusCode.NO_FACE_DETECTED)

                case (_, fc) if 0.0 < fc <= 1.0 and fc < threshold:
                    encoded[file] = Encoding.StatusCode.NO_FACE_ACCEPTED.value
                    process_encoding_error(file, Encoding.StatusCode.NO_FACE_ACCEPTED)

                case _:
                    encoded[file] = result[0]["embedding"]
                    added_cnt += 1

        except TypeError as e:
            logger.exception(e)
            encoded[file] = Encoding.StatusCode.GENERIC_ERROR.value
            process_encoding_error(file, Encoding.StatusCode.GENERIC_ERROR)
        except ResourceNotFoundError:
            encoded[file] = Encoding.StatusCode.NO_FILE_FOUND.value
            process_encoding_error(file, Encoding.StatusCode.NO_FILE_FOUND)

    return encoded, added_cnt, existing_cnt


def dedupe_images(  # noqa 901
    files0: list[str],
    files1: list[str],
    encodings: EncodingType,
    ignored_pairs: IgnoredPairType,
    config: dict[str, Any] | None = None,
) -> FindingType:
    findings = defaultdict(list)
    options = config.get("deduplicate") if config else {}

    for i, file1 in enumerate(files0):
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
            if (confidence := res.get("confidence", 0)) >= config.get("duplicate_confidence_threshold", 0):
                findings[file1].append([file2, confidence / 100])

    results: FindingType = []

    for img, duplicates in findings.items():
        for dup in duplicates:
            if is_facial_error(dup[0]):
                results.append((img, "", 0, Encoding.StatusCode(dup[0]).value))
            else:
                results.append((img, dup[0], dup[1], Encoding.StatusCode.DEDUPLICATE_SUCCESS.value))

    return results
