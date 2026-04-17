from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from ofiq import OFIQ
from azure.core.exceptions import ResourceNotFoundError
from deepface import DeepFace
from deepface.commons.image_utils import load_image_from_base64
from deepface.modules.verification import find_confidence, find_distance, find_threshold
from django.db import transaction
from numpy import ndarray


from hope_dedup_engine.apps.api.models import Encoding, Finding, DeduplicationSet
from hope_dedup_engine.apps.api.utils.data_url import parse_data_url
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager
from hope_dedup_engine.apps.faces.services.quality import get_active_thresholds, check_image_quality

if TYPE_CHECKING:
    from uuid import UUID
    from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig

logger = logging.getLogger(__name__)


Embedding = list[float]


def encode_face(
    data: ndarray,
    face_confidence_threshold: float,
    model_name: str,
    detector_backend: str,
    align: bool = True,
) -> tuple[Embedding | None, Encoding.StatusCode | None]:
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
            return None, Encoding.StatusCode.NO_FACE_DETECTED
        case [_, _, *_]:
            return None, Encoding.StatusCode.MULTIPLE_FACES_DETECTED
        case [face]:
            match fc := float(face.get("face_confidence") or 0.0):
                case 0.0:
                    return None, Encoding.StatusCode.NO_FACE_DETECTED
                case _ if fc < face_confidence_threshold:
                    return None, Encoding.StatusCode.FACE_NOT_ACCEPTED
                case _:
                    return face["embedding"], None

    return None, Encoding.StatusCode.GENERIC_ERROR


def encode_faces(
    ds: DeduplicationSet,
    encoding_ids: list[UUID],
    config: DeduplicationSetConfig,
) -> None:
    storage = ImagesStorageManager()
    active_thresholds = get_active_thresholds(config)
    config_snapshot = config.as_dict()

    ofiq = None
    if active_thresholds:
        ofiq = OFIQ()
    encodings = Encoding.objects.filter(id__in=encoding_ids).iterator(chunk_size=25)

    for encoding in encodings:
        with transaction.atomic():
            try:
                encoding.embedding_status_code = None
                encoding.image_quality_scores = None
                image_data = (
                    load_image_from_base64(encoding.filename)
                    if parse_data_url(encoding.filename)
                    else storage.load_image(encoding.filename)
                )

                if ofiq is not None:
                    qr = check_image_quality(ofiq, image_data, active_thresholds)
                    encoding.image_quality_scores = qr.scores

                    if not qr.face_detected:
                        encoding.embedding_status_code = Encoding.StatusCode.NO_FACE_DETECTED
                    elif not qr.passed:
                        encoding.embedding_status_code = Encoding.StatusCode.BAD_IMAGE_QUALITY

                if encoding.embedding_status_code is None:
                    encoding.embedding, encoding.embedding_status_code = encode_face(
                        image_data,
                        config.face_detection_confidence_threshold,
                        config.recognition_model,
                        config.detector_backend,
                    )

            except ResourceNotFoundError:
                encoding.embedding_status_code = Encoding.StatusCode.FILE_NOT_FOUND.value
            except Exception as e:
                logger.exception(e)
                encoding.embedding_status_code = Encoding.StatusCode.GENERIC_ERROR.value

            encoding.save(update_fields=["embedding", "embedding_status_code", "image_quality_scores"])

            if encoding.embedding_status_code is not None:
                Finding.objects.update_or_create(
                    deduplication_set=ds,
                    first_encoding=encoding,
                    second_encoding=None,
                    defaults={
                        "score": 0,
                        "status_code": encoding.embedding_status_code,
                        "config": config_snapshot,
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
    config: DeduplicationSetConfig,
    chunk_size: int,
) -> list[tuple[int, int, float]]:
    """
    Find duplicate pairs using chunked matrix distance calculations.

    Compares current encodings against all (current + approved) using vectorized
    operations. Returns list of (first_id, second_id, confidence) for matches.
    """
    model_name = config.recognition_model
    distance_metric = config.distance_metric
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
        deduplication_set__state=DeduplicationSet.State.APPROVED,
        deduplication_set__group=deduplication_set.group,
        embedding__isnull=False,
    ).order_by("id")

    all_emb, all_ids, all_filenames, n_current = load_encodings(current_qs, approved_qs, embedding_dim, chunk_size)

    duplicates = find_duplicate_pairs(all_emb, all_ids, all_filenames, n_current, config, chunk_size)

    if duplicates:
        config_snapshot = config.as_dict()
        findings = [
            Finding(
                deduplication_set=deduplication_set,
                first_encoding_id=first_id,
                second_encoding_id=second_id,
                score=confidence / 100,
                status_code=Encoding.StatusCode.DEDUPLICATE_SUCCESS,
                config=config_snapshot,
            )
            for first_id, second_id, confidence in duplicates
        ]

        Finding.objects.bulk_create(
            findings,
            update_conflicts=True,
            unique_fields=["deduplication_set", "first_encoding", "second_encoding"],
            update_fields=["score", "status_code", "config", "updated_at"],
        )

    return len(duplicates)
