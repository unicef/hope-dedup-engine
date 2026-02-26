import logging
from uuid import UUID
from typing import Any, Mapping

import numpy as np
from azure.core.exceptions import ResourceNotFoundError
from deepface import DeepFace
from deepface.commons.image_utils import load_image_from_base64
from deepface.modules.verification import find_confidence, find_distance, find_threshold
from django.db import transaction
from numpy import ndarray

from hope_dedup_engine.apps.api.models import Encoding, Finding, DeduplicationSet
from hope_dedup_engine.apps.api.utils.data_url import parse_data_url
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager

logger = logging.getLogger(__name__)


Embedding = list[float]


def face_coverage_ratio(*, fa: Mapping[str, Any], img_w: int, img_h: int) -> float:
    if (img_box := float(img_w) * float(img_h)) <= 0.0:
        return 0.0
    if (w := float(fa.get("w") or 0.0)) <= 0.0 or (h := float(fa.get("h") or 0.0)) <= 0.0:
        return 0.0
    return (w * h) / img_box


def encode_face(  # noqa: PLR0911, PLR0913
    data: ndarray,
    face_confidence_threshold: float,
    face_coverage_threshold: float,
    model_name: str,
    detector_backend: str,
    align: bool,
) -> tuple[Embedding | None, Encoding.StatusCode | None, float | None]:
    # we use max_faces=2 not to waste time searching for more faces than we need
    # we use enforce_detection=False not to raise exception when no face found
    result = DeepFace.represent(
        data,
        max_faces=2,
        enforce_detection=False,
        model_name=model_name,
        detector_backend=detector_backend,
        align=align,
    )

    match result:
        case []:
            return None, Encoding.StatusCode.NO_FACE_DETECTED, None
        case [_, _, *_]:
            return None, Encoding.StatusCode.MULTIPLE_FACES_DETECTED, None
        case [face]:
            match fc := float(face.get("face_confidence") or 0.0):
                case 0.0:
                    return None, Encoding.StatusCode.NO_FACE_DETECTED, None
                case _ if fc < face_confidence_threshold:
                    return None, Encoding.StatusCode.FACE_NOT_ACCEPTED, None
                case _:
                    if not (fa := face.get("facial_area")):
                        return None, Encoding.StatusCode.GENERIC_ERROR, None
                    coverage_raw = face_coverage_ratio(fa=fa, img_w=data.shape[1], img_h=data.shape[0])
                    coverage = round(coverage_raw, 4)
                    if coverage_raw < face_coverage_threshold:
                        return None, Encoding.StatusCode.INSUFFICIENT_FACE_COVERAGE, coverage
                    return face["embedding"], None, coverage

    return None, Encoding.StatusCode.GENERIC_ERROR, None


def encode_faces(  # noqa: PLR0913
    ds: DeduplicationSet,
    encoding_ids: list[UUID],
    face_confidence_threshold: float,
    face_coverage_threshold: float,
    model_name: str,
    detector_backend: str,
    align: bool,
) -> None:
    storage = ImagesStorageManager()

    encodings = Encoding.objects.filter(id__in=encoding_ids).iterator(chunk_size=25)

    for encoding in encodings:
        with transaction.atomic():
            try:
                encoding.embedding_status_code = None
                image_data = (
                    load_image_from_base64(encoding.filename)
                    if parse_data_url(encoding.filename)
                    else storage.load_image(encoding.filename)
                )
                encoding.embedding, encoding.embedding_status_code, encoding.face_coverage = encode_face(
                    image_data,
                    face_confidence_threshold,
                    face_coverage_threshold,
                    model_name,
                    detector_backend,
                    align,
                )

            except TypeError as e:
                logger.exception(e)
                encoding.embedding_status_code = Encoding.StatusCode.GENERIC_ERROR.value
            except ResourceNotFoundError:
                encoding.embedding_status_code = Encoding.StatusCode.FILE_NOT_FOUND.value

            encoding.save(update_fields=["embedding", "embedding_status_code", "face_coverage"])

            if encoding.embedding_status_code is not None:
                Finding.objects.update_or_create(
                    deduplication_set=ds,
                    first_encoding=encoding,
                    second_encoding=None,
                    defaults={
                        "score": 0,
                        "status_code": encoding.embedding_status_code,
                    },
                )


def dedupe_all(
    deduplication_set: DeduplicationSet,
    duplicate_confidence_threshold: float,
    model_name: str,
    distance_metric: str,
    chunk_size: int = 1000,
) -> int:
    """
    Deduplicate all encodings in a deduplication set using matrix operations.

    This function uses vectorized distance calculations instead of per-pair DeepFace.verify()
    calls, providing ~10,000x performance improvement for large datasets.

    Args:
        deduplication_set: The deduplication set to process
        duplicate_confidence_threshold: Minimum confidence (0-100) to create a finding
        model_name: DeepFace model name (e.g., "Facenet512")
        distance_metric: Distance metric (e.g., "cosine")
        chunk_size: Number of encodings to process per chunk (memory/performance trade-off)

    Returns:
        Number of findings created

    """
    encodings = list(
        deduplication_set.encoding_set.filter(
            embedding__isnull=False,
        )
        .values_list("id", "filename", "embedding")
        .order_by("id")
    )

    if not encodings:
        return 0

    approved_encodings = list(
        Encoding.objects.filter(
            state=Encoding.State.APPROVED,
            deduplication_set__state=DeduplicationSet.State.INACTIVE,
            deduplication_set__group=deduplication_set.group,
            embedding__isnull=False,
        )
        .values_list("id", "filename", "embedding")
        .order_by("id")
    )

    # Build parallel arrays for fast lookup
    ids = [enc[0] for enc in encodings]
    filenames = [enc[1] for enc in encodings]
    emb = np.array([enc[2] for enc in encodings], dtype=np.float32)
    n_current = len(encodings)

    if approved_encodings:
        approved_ids = [enc[0] for enc in approved_encodings]
        approved_filenames = [enc[1] for enc in approved_encodings]
        approved_emb = np.array([enc[2] for enc in approved_encodings], dtype=np.float32)

        all_emb = np.vstack([emb, approved_emb])
        all_ids = ids + approved_ids
        all_filenames = filenames + approved_filenames
    else:
        all_emb = emb
        all_ids = ids
        all_filenames = filenames

    ignored_pairs = deduplication_set.get_ignored_pairs()

    # Get distance threshold from DeepFace. This could be provided as a constance config variable.
    pretuned_threshold = find_threshold(model_name, distance_metric)

    findings_to_create = []

    for start in range(0, n_current, chunk_size):
        chunk_emb = emb[start : start + chunk_size]
        # find_distance returns shape (n_all, chunk_size), transpose to (chunk_size, n_all)
        distances = find_distance(chunk_emb, all_emb, distance_metric).T

        # Find pairs below distance threshold (verified pairs)
        rows, cols = np.where(distances <= pretuned_threshold)

        for r, c in zip(rows, cols, strict=True):
            global_r = start + r

            if c < n_current and global_r >= c:
                continue  # Skip lower triangle + diagonal for self-comparison

            if frozenset([filenames[global_r], all_filenames[c]]) in ignored_pairs:
                continue

            # Calculate confidence for verified pairs only
            distance = float(distances[r, c])
            confidence = find_confidence(distance, model_name, distance_metric, verified=True)

            if confidence >= duplicate_confidence_threshold:
                findings_to_create.append(
                    Finding(
                        deduplication_set=deduplication_set,
                        first_encoding_id=ids[global_r],
                        second_encoding_id=all_ids[c],
                        score=confidence / 100,  # Store as 0-1
                        status_code=Encoding.StatusCode.DEDUPLICATE_SUCCESS,
                    )
                )

    if findings_to_create:
        Finding.objects.bulk_create(
            findings_to_create,
            update_conflicts=True,
            unique_fields=["deduplication_set", "first_encoding", "second_encoding"],
            update_fields=["score", "status_code", "updated_at"],
        )

    return len(findings_to_create)
