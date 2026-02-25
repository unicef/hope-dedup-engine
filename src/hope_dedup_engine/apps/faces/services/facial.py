import logging
from uuid import UUID
from typing import Any, Mapping
from azure.core.exceptions import ResourceNotFoundError
from deepface import DeepFace
from deepface.commons.image_utils import load_image_from_base64
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

    encodings = Encoding.objects.filter(id__in=encoding_ids)

    with transaction.atomic():
        for encoding in encodings:
            try:
                # we can have the previous status code set (i.e., system error)
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


def dedupe_images(  # noqa: PLR0913
    deduplication_set: DeduplicationSet,
    encodings0: list[Encoding],
    encodings1: list[Encoding],
    ignored_pairs: set[frozenset[str]],
    duplicate_confidence_threshold: float,
    model_name: str,
    detector_backend: str,
    distance_metric: str,
    align: bool,
    silent: bool,
) -> None:
    with transaction.atomic():
        for i, encoding0 in enumerate(encodings0):
            if encodings0 == encodings1:
                encodings1_ = encodings1[i + 1 :]
            else:
                encodings1_ = encodings1

            for encoding1 in encodings1_:
                if {encoding0.filename, encoding1.filename} in ignored_pairs:
                    continue
                res = DeepFace.verify(
                    encoding0.embedding,
                    encoding1.embedding,
                    model_name=model_name,
                    detector_backend=detector_backend,
                    distance_metric=distance_metric,
                    align=align,
                    silent=silent,
                )
                if (confidence := res.get("confidence", 0)) >= duplicate_confidence_threshold:
                    Finding.objects.update_or_create(
                        deduplication_set=deduplication_set,
                        first_encoding=encoding0,
                        second_encoding=encoding1,
                        defaults={
                            "score": confidence / 100,
                            "status_code": Encoding.StatusCode.DEDUPLICATE_SUCCESS,
                        },
                    )
