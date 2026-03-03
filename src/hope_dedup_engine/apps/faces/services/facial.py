from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Mapping

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

if TYPE_CHECKING:
    from uuid import UUID
    from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig

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


def load_encodings(
    current_qs,
    approved_qs,
    embedding_dim: int,
    chunk_size: int,
) -> tuple[np.ndarray, list, list, int]:
    """
    Stream encodings from DB into pre-allocated numpy arrays.

    Returns (all_emb, all_ids, all_filenames, n_current) where current encodings
    occupy indices [0:n_current] and approved encodings occupy [n_current:].
    """
    n_current = current_qs.count()
    n_approved = approved_qs.count()
    n_all = n_current + n_approved

    all_emb = np.empty((n_all, embedding_dim), dtype=np.float32)
    all_ids: list = []
    all_filenames: list = []

    for i, (enc_id, filename, embedding) in enumerate(
        current_qs.values_list("id", "filename", "embedding").iterator(chunk_size=chunk_size)
    ):
        all_ids.append(enc_id)
        all_filenames.append(filename)
        all_emb[i] = embedding

    if n_approved > 0:
        for i, (enc_id, filename, embedding) in enumerate(
            approved_qs.values_list("id", "filename", "embedding").iterator(chunk_size=chunk_size)
        ):
            all_ids.append(enc_id)
            all_filenames.append(filename)
            all_emb[n_current + i] = embedding

    return all_emb, all_ids, all_filenames, n_current


def find_duplicate_pairs(  # noqa
    all_emb: np.ndarray,
    all_ids: list,
    all_filenames: list,
    n_current: int,
    ignored_pairs: set,
    config: DeduplicationSetConfig,
    chunk_size: int,
) -> list[tuple[int, int, float]]:
    """
    Find duplicate pairs using chunked matrix distance calculations.

    Compares current encodings against all (current + approved) using vectorized
    operations. Returns list of (first_id, second_id, confidence) for matches.
    """
    model_name = config.deduplicate.model_name
    distance_metric = config.deduplicate.distance_metric
    confidence_threshold = config.duplicate_confidence_threshold

    distance_threshold = find_threshold(model_name, distance_metric)
    duplicates = []

    for start in range(0, n_current, chunk_size):
        chunk_emb = all_emb[start : start + chunk_size]
        distances = find_distance(all_emb, chunk_emb, distance_metric)

        rows, cols = np.where(distances <= distance_threshold)

        for r, c in zip(rows, cols, strict=True):
            global_r = start + r

            if c < n_current and global_r >= c:
                continue

            if frozenset([all_filenames[global_r], all_filenames[c]]) in ignored_pairs:
                continue

            distance = float(distances[r, c])
            confidence = find_confidence(distance, model_name, distance_metric, verified=True)

            if confidence >= confidence_threshold:
                duplicates.append((all_ids[global_r], all_ids[c], confidence))

    return duplicates


def dedupe_all(
    deduplication_set: DeduplicationSet,
    config: DeduplicationSetConfig,
    chunk_size: int = 1000,
) -> int:
    """
    Deduplicate all encodings in a deduplication set using matrix operations.

    Uses vectorized distance calculations instead of per-pair DeepFace.verify()
    calls, providing significant performance improvement for large datasets.
    """
    current_qs = deduplication_set.encoding_set.filter(
        embedding__isnull=False,
    ).order_by("id")

    n_current = current_qs.count()
    if n_current == 0:
        return 0

    first_embedding = current_qs.values_list("embedding", flat=True).first()
    embedding_dim = len(first_embedding)

    approved_qs = Encoding.objects.filter(
        state=Encoding.State.APPROVED,
        deduplication_set__state=DeduplicationSet.State.INACTIVE,
        deduplication_set__group=deduplication_set.group,
        embedding__isnull=False,
    ).order_by("id")

    all_emb, all_ids, all_filenames, n_current = load_encodings(current_qs, approved_qs, embedding_dim, chunk_size)

    ignored_pairs = deduplication_set.get_ignored_pairs()

    duplicates = find_duplicate_pairs(all_emb, all_ids, all_filenames, n_current, ignored_pairs, config, chunk_size)

    if duplicates:
        findings = [
            Finding(
                deduplication_set=deduplication_set,
                first_encoding_id=first_id,
                second_encoding_id=second_id,
                score=confidence / 100,
                status_code=Encoding.StatusCode.DEDUPLICATE_SUCCESS,
            )
            for first_id, second_id, confidence in duplicates
        ]

        Finding.objects.bulk_create(
            findings,
            update_conflicts=True,
            unique_fields=["deduplication_set", "first_encoding", "second_encoding"],
            update_fields=["score", "status_code", "updated_at"],
        )

    return len(duplicates)
