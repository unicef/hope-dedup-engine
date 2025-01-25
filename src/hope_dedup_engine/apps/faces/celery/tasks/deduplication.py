from collections.abc import Iterator
from itertools import combinations
from typing import Any

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.faces.services.facial import (
    encode_faces,
    find_similar_faces,
)
from hope_dedup_engine.config.celery import app
from hope_dedup_engine.constants import FacialError
from hope_dedup_engine.types import EntityEmbedding, Filename, SortedTuple
from hope_dedup_engine.utils.celery.task_result import wrapped


@app.task
@wrapped
def get_deduplication_set_image_files(deduplication_set_id: str) -> list[Filename]:
    # TODO: optimize it calculating on DB side
    deduplication_set: DeduplicationSet = DeduplicationSet.objects.get(
        pk=deduplication_set_id
    )
    files = set(deduplication_set.image_set.values_list("filename", flat=True))
    processed_files = deduplication_set.encodings.keys()
    return list(files - processed_files)


@app.task
@wrapped
def encode_images(
    images: list[str],
    deduplication_set_id: str,
    encoding_config: dict[str, Any],
) -> None:
    """Encode faces in a chunk of files."""
    encodings, errors = encode_faces(images, encoding_config)
    deduplication_set: DeduplicationSet = DeduplicationSet.objects.get(
        pk=deduplication_set_id
    )
    deduplication_set.update_encodings(encodings)
    deduplication_set.update_encoding_errors(errors)


@app.task
@wrapped
def get_deduplication_set_embedding_pairs(
    deduplication_set_id: str,
) -> Iterator[tuple[EntityEmbedding, EntityEmbedding]]:
    deduplication_set: DeduplicationSet = DeduplicationSet.objects.get(
        pk=deduplication_set_id
    )

    entity_embeddings = tuple(
        (reference_pk, deduplication_set.encodings[filename])
        for reference_pk, filename in deduplication_set.image_set.values_list(
            "reference_pk", "filename"
        )
        if filename in deduplication_set.encodings
    )

    return combinations(entity_embeddings, 2)


@app.task
@wrapped
def filter_ignored_pairs(
    embedding_pairs: list[tuple[EntityEmbedding, EntityEmbedding]],
    deduplication_set_id: str,
) -> list[tuple[EntityEmbedding, EntityEmbedding]]:
    deduplication_set: DeduplicationSet = DeduplicationSet.objects.get(
        pk=deduplication_set_id
    )
    ignored_pairs = deduplication_set.get_ignored_pairs()
    filtered = []
    for embedding_pair in embedding_pairs:
        first, second = embedding_pair
        first_reference_pk, _ = first
        second_reference_pk, _ = second
        if SortedTuple((first_reference_pk, second_reference_pk)) not in ignored_pairs:
            filtered.append(embedding_pair)

    return filtered


@app.task
@wrapped
def find_duplicates(
    embedding_pairs: list[tuple[EntityEmbedding, EntityEmbedding]],
    deduplication_set_id: str,
    deduplicate_config: dict[str, Any],
) -> None:
    """Deduplicate faces in a chunk of files."""
    deduplication_set = DeduplicationSet.objects.get(pk=deduplication_set_id)
    findings = find_similar_faces(
        embedding_pairs,
        dedupe_threshold=deduplicate_config.get("threshold"),
        options=deduplicate_config,
    )
    deduplication_set.update_findings(findings)


@app.task
@wrapped
def save_encoding_errors_in_findings(deduplication_set_id: str) -> None:
    deduplication_set: DeduplicationSet = DeduplicationSet.objects.get(
        pk=deduplication_set_id
    )
    embedding_errors = [
        (reference_pk, FacialError(deduplication_set.encoding_errors[filename]))
        for reference_pk, filename in deduplication_set.image_set.values_list(
            "reference_pk", "filename"
        )
        if filename in deduplication_set.encoding_errors
    ]
    deduplication_set.update_finding_errors(embedding_errors)
