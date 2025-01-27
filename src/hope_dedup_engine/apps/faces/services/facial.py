import logging
from collections.abc import Generator, Iterable
from itertools import chain
from typing import Any, cast

from django.db import transaction

from deepface import DeepFace

from hope_dedup_engine.apps.api.models import DeduplicationSet, Finding, Image
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager
from hope_dedup_engine.types import (
    Embedding,
    EntityEmbedding,
    EntityEmbeddingError,
    EntityIgnoredPair,
    Filename,
    ImageEmbedding,
    ImageEmbeddingError,
    Score,
    SortedTuple,
)

logger = logging.getLogger(__name__)


def encode_faces(
    filenames: list[Filename],
    options=None,
) -> tuple[list[ImageEmbedding], list[ImageEmbeddingError]]:
    storage = ImagesStorageManager()
    images = storage.get_files()

    embeddings = []
    errors = []

    for filename in filenames:
        if filename not in images:
            errors.append((filename, Finding.StatusCode.NO_FILE_FOUND.name))
            continue

        try:
            result = DeepFace.represent(storage.load_image(filename), **(options or {}))
            if len(result) > 1:
                errors.append(
                    (filename, Finding.StatusCode.MULTIPLE_FACES_DETECTED.name)
                )
            else:
                embeddings.append((filename, cast(list[float], result[0]["embedding"])))
        except TypeError as e:
            logger.exception(e)
            errors.append((filename, Finding.StatusCode.GENERIC_ERROR.name))
        except ValueError:
            errors.append((filename, Finding.StatusCode.NO_FACE_DETECTED.name))

    return embeddings, errors


EncodedFace = tuple[str, str | list[float]]


def face_similarity(first: Embedding, second: Embedding, **options: Any) -> float:
    result = DeepFace.verify(first, second, **options)
    return float(1 - result["distance"])


def find_similar_faces(
    embedding_pairs: Iterable[tuple[EntityEmbedding, EntityEmbedding]],
    dedupe_threshold: float,
    options: dict[str, Any],
) -> Generator[tuple[EncodedFace, EncodedFace, float]]:
    for first, second in embedding_pairs:
        first_filename, first_embedding = first
        second_filename, second_embedding = second
        similarity = face_similarity(first_embedding, second_embedding, **options)
        if similarity >= dedupe_threshold:
            yield first_filename, second_filename, similarity


def get_referencepk_filename_pairs(
    deduplication_set: DeduplicationSet,
) -> Generator[tuple[str, str], None, None]:
    queryset = Image.objects.filter(deduplication_set=deduplication_set).values_list(
        "reference_pk", "filename"
    )
    for reference_pk, filename in queryset.iterator():
        yield reference_pk, filename


def get_ignored_pairs(deduplication_set: DeduplicationSet) -> set[EntityIgnoredPair]:
    referencepk_to_filename = dict(get_referencepk_filename_pairs(deduplication_set))
    return set(
        chain(
            map(
                SortedTuple,
                (
                    (
                        referencepk_to_filename[first],
                        referencepk_to_filename[second],
                    )
                    for first, second in deduplication_set.ignoredreferencepkpair_set.values_list(
                        "first", "second"
                    )
                ),
            ),
            map(
                SortedTuple,
                deduplication_set.ignoredfilenamepair_set.values_list(
                    "first", "second"
                ),
            ),
        )
    )


def bulk_create_findings(findings: Iterable[Finding]) -> None:
    findings_list = list(findings)
    if findings_list:
        with transaction.atomic():
            Finding.objects.bulk_create(findings_list, ignore_conflicts=True)
        logger.info(f"Created {len(findings_list)} findings.")


def update_findings(
    deduplication_set: DeduplicationSet,
    findings: list[tuple[EntityEmbedding, EntityEmbedding, Score]],
) -> None:
    filename_to_reference_pk = {
        filename: reference_pk
        for reference_pk, filename in get_referencepk_filename_pairs(deduplication_set)
    }
    findings_to_create = (
        Finding(
            deduplication_set=deduplication_set,
            first_reference_pk=filename_to_reference_pk.get(first_filename),
            first_filename=first_filename,
            second_reference_pk=filename_to_reference_pk.get(second_filename),
            second_filename=second_filename,
            score=score,
        )
        for first_filename, second_filename, score in findings
    )
    bulk_create_findings(findings_to_create)


def update_finding_errors(
    deduplication_set: DeduplicationSet, encoding_errors: list[EntityEmbeddingError]
):
    errors_to_create = (
        Finding(
            deduplication_set=deduplication_set,
            first_reference_pk=reference_pk,
            first_filename=filename,
            status_code=Finding.StatusCode[error].value,
        )
        for reference_pk, filename, error in encoding_errors
    )
    bulk_create_findings(errors_to_create)
