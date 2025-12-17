import contextlib
from itertools import combinations
from typing import NamedTuple

from constance import config
from deepface import DeepFace
from django.db.models import QuerySet
from numpy import ndarray

from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager


class Detection(NamedTuple):
    encoding: Encoding
    confidence: float
    embedding: ndarray


def detect_face(encoding: Encoding, image_storage_manager: ImagesStorageManager | None = None) -> Detection | None:
    if image_storage_manager is None:
        image_storage_manager = ImagesStorageManager()

    with contextlib.suppress(Exception):
        representation = DeepFace.represent(
            image_storage_manager.load_image(encoding.filename),
            model_name=config.DEFAULT_RECOGNITION_MODEL,
            detector_backend=config.DEFAULT_DETECTOR_BACKEND,
            max_faces=2,
            enforce_detection=False,
        )
        if len(representation) == 1:
            return Detection(
                encoding=encoding,
                confidence=100 * float(representation[0]["face_confidence"]),
                embedding=representation[0]["embedding"],
            )

    return None


class Finding(NamedTuple):
    confidence: float
    encoding0: Encoding
    encoding1: Encoding


def deduplicate(queryset: QuerySet[Encoding]) -> list[Finding]:
    image_storage_manager = ImagesStorageManager()
    detections = [
        detection
        for encoding in queryset
        if (detection := detect_face(encoding, image_storage_manager))
        and detection.confidence >= config.DEFAULT_FACE_DETECTION_CONFIDENCE_THRESHOLD
    ]

    findings = []
    for pair in combinations(detections, 2):
        detection0, detection1 = pair
        output = DeepFace.verify(
            detection0.embedding,
            detection1.embedding,
            model_name=config.DEFAULT_RECOGNITION_MODEL,
            detector_backend=config.DEFAULT_DETECTOR_BACKEND,
            distance_metric=config.DEFAULT_DISTANCE_METRIC,
        )
        findings.append(
            Finding(confidence=output["confidence"], encoding0=detection0.encoding, encoding1=detection1.encoding)
        )

    return findings
