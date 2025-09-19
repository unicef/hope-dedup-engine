import logging
from collections import defaultdict
from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from deepface import DeepFace
import numpy as np
from numpy.linalg import norm

from hope_dedup_engine.apps.api.models import Image
from hope_dedup_engine.apps.faces.managers.storage import get_storage_manager
from hope_dedup_engine.apps.faces.utils import is_facial_error, report_long_execution
from hope_dedup_engine.type_aliases import EncodingType, FindingType, IgnoredPairType

logger = logging.getLogger(__name__)


def default_progress(*args):
    return True


def encode_faces(
    files: list[str],
    options=None,
    pre_encodings=None,
    progress=None,
) -> tuple[EncodingType, list[str], int, int]:
    if not callable(progress):
        progress = default_progress

    with report_long_execution("get_storage_manager()"):
        storage = get_storage_manager()

    encoded = {}
    if pre_encodings:
        with report_long_execution("encoded.update(pre_encodings)"):
            encoded.update(pre_encodings)
    added_cnt = existing_cnt = 0
    newly_encoded_files = []
    for file in files:
        with report_long_execution("progress()"):
            progress()
        if file in encoded:
            existing_cnt += 1
            continue
        newly_encoded_files.append(file)
        try:
            with report_long_execution("DeepFace.represent(storage.load_image(file), **(options or {}))"):
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
        except ResourceNotFoundError:
            encoded[file] = Image.StatusCode.NO_FILE_FOUND.name

    return encoded, newly_encoded_files, added_cnt, existing_cnt


def dedupe_images(  # noqa 901
    encodings1: EncodingType,
    encodings2: EncodingType,
    ignored_pairs: IgnoredPairType,
    dedupe_threshold: float,
    options: dict[str, Any] = None,
    progress=None,
) -> FindingType:
    if not callable(progress):
        progress = default_progress

    findings = defaultdict(list)
    all_encodings = {**encodings1, **encodings2}
    encodings_np = {file: np.array(enc) for file, enc in all_encodings.items() if not is_facial_error(enc)}
    encodings_norm = {file: norm(enc) for file, enc in encodings_np.items()}

    files1 = list(encodings1.keys())

    def compare_and_find(file1: str, file2: str) -> None:
        if (file1, file2) in ignored_pairs or (file2, file1) in ignored_pairs:
            return

        if file1 not in encodings_np or file2 not in encodings_np:
            return

        norm1 = encodings_norm[file1]
        norm2 = encodings_norm[file2]

        if norm1 == 0 or norm2 == 0:
            return

        enc1_np = encodings_np[file1]
        enc2_np = encodings_np[file2]

        similarity = float(np.dot(enc1_np, enc2_np) / (norm1 * norm2))

        if similarity >= dedupe_threshold:
            findings[file1].append([file2, similarity])

    if id(encodings1) == id(encodings2):  # Intra-chunk comparison
        for i, file1 in enumerate(files1):
            progress()
            enc1 = encodings1[file1]
            if is_facial_error(enc1):
                if file1 not in findings:
                    findings[file1].append([enc1, None])
                continue

            for j in range(i + 1, len(files1)):
                file2 = files1[j]
                compare_and_find(file1, file2)
    else:  # Inter-chunk comparison
        files2 = list(encodings2.keys())
        for file1 in files1:
            progress()
            enc1 = encodings1[file1]
            if is_facial_error(enc1):
                if file1 not in findings:
                    findings[file1].append([enc1, None])
                continue

            for file2 in files2:
                compare_and_find(file1, file2)

    results: FindingType = []

    for img, duplicates in findings.items():
        for dup in duplicates:
            if is_facial_error(dup[0]):
                results.append((img, "", 0, Image.StatusCode[dup[0]].value))
            else:
                results.append((img, dup[0], dup[1], Image.StatusCode.DEDUPLICATE_SUCCESS.value))

    return results
