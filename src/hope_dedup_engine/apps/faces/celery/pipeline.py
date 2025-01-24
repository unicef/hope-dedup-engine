from typing import Any

from celery.canvas import Signature

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.faces.celery.tasks.deduplication import (
    deduplication_set_embedding_pairs,
    deduplication_set_image_files,
    encode_images,
    filter_ignored_pairs,
    find_duplicates,
    save_encoding_errors_in_findings,
)
from hope_dedup_engine.utils.celery.utility_tasks import parallelize


def image_pipeline(
    deduplication_set: DeduplicationSet, config: dict[str, Any]
) -> Signature:
    encode_images_pipeline = parallelize.si(
        deduplication_set_image_files.s(deduplication_set.id),
        encode_images.s(config),
        100,
    )
    find_duplicates_pipeline = parallelize.si(
        deduplication_set_embedding_pairs.s(deduplication_set.id),
        filter_ignored_pairs.s(deduplication_set.id) | find_duplicates.s(config),
        100,
    )

    return (
        encode_images_pipeline
        | find_duplicates_pipeline
        | save_encoding_errors_in_findings.s(deduplication_set.id)
    )
