from typing import Any

from celery.canvas import Signature

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.faces.celery.tasks.deduplication import (
    encode_images,
    filter_ignored_pairs,
    find_duplicates,
    get_deduplication_set_embedding_pairs,
    get_deduplication_set_image_files,
    save_encoding_errors_in_findings,
)
from hope_dedup_engine.utils.celery.utility_tasks import parallelize

IMAGE_ENCODING_BATCH_SIZE = 50
DUPLICATE_FINDING_BATCH_SIZE = 200


def image_pipeline(
    deduplication_set: DeduplicationSet, config: dict[str, Any]
) -> Signature:
    encode_images_pipeline = parallelize.si(
        get_deduplication_set_image_files.s(deduplication_set.id),
        encode_images.s(deduplication_set.id, config.get("encoding")),
        IMAGE_ENCODING_BATCH_SIZE,
    )
    find_duplicates_pipeline = parallelize.si(
        get_deduplication_set_embedding_pairs.s(deduplication_set.id),
        filter_ignored_pairs.s(deduplication_set.id)
        | find_duplicates.s(deduplication_set.id, config.get("deduplicate", {})),
        DUPLICATE_FINDING_BATCH_SIZE,
    )

    return (
        encode_images_pipeline
        | find_duplicates_pipeline
        | save_encoding_errors_in_findings.si(deduplication_set.id)
    )
