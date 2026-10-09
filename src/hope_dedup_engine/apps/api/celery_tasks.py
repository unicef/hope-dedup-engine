import logging
from datetime import timedelta

from celery import shared_task
from constance import config
from django.db.models import Model, QuerySet
from django.utils import timezone

from hope_dedup_engine.apps.api.deduplication.process import (  # noqa: F401
    find_duplicates,
)
from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding, Finding

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


@shared_task
def not_a_task() -> None:
    pass


def _delete_in_batches[ModelT: Model](queryset: QuerySet[ModelT], *, batch_size: int = _BATCH_SIZE) -> None:
    """Delete a queryset in primary-key batches so one run cannot hold a long lock."""
    while True:
        batch_ids = list(queryset.order_by("pk").values_list("pk", flat=True)[:batch_size])
        if not batch_ids:
            return
        queryset.filter(pk__in=batch_ids).delete()


@shared_task
def cleanup_redundant_data(retention_days: int | None = None) -> dict[str, int]:
    """Delete findings HOPE already has, and data from old rejected deduplication sets.

    A finding counts as sent to HOPE when its deduplication set is approved: HOPE
    reads the findings and then approves the set. Encodings on approved sets are
    kept, because later runs in the same group compare new images against them.

    Rejected sets are removed together with their findings and encodings. Image
    files are removed by the encoding post_delete signal after the transaction commits.

    Age comes from the deduplication set ``updated_at``, which changes when the
    set is approved or rejected. Anything updated more recently than
    ``retention_days`` is left in place. Pass ``retention_days`` to override the
    ``CLEANUP_RETENTION_DAYS`` constance setting (60 days, about two months).
    """
    days = config.CLEANUP_RETENTION_DAYS if retention_days is None else retention_days
    days = int(days)
    if days < 1:
        raise ValueError(f"retention_days must be at least 1, got {days}")

    cutoff = timezone.now() - timedelta(days=days)
    old_approved_sets = DeduplicationSet.objects.filter(
        state=DeduplicationSet.State.APPROVED,
        updated_at__lt=cutoff,
    )
    old_rejected_sets = DeduplicationSet.objects.filter(
        state=DeduplicationSet.State.REJECTED,
        updated_at__lt=cutoff,
    )
    sent_findings = Finding.objects.filter(deduplication_set__in=old_approved_sets)
    rejected_findings = Finding.objects.filter(deduplication_set__in=old_rejected_sets)
    rejected_encodings = Encoding.objects.filter(deduplication_set__in=old_rejected_sets)

    counts = {
        "findings_sent_to_hope": sent_findings.count(),
        "rejected_findings": rejected_findings.count(),
        "rejected_encodings": rejected_encodings.count(),
        "rejected_sets": old_rejected_sets.count(),
    }

    _delete_in_batches(sent_findings)
    _delete_in_batches(rejected_findings)
    _delete_in_batches(rejected_encodings)
    _delete_in_batches(old_rejected_sets)

    logger.info("Cleaned up redundant data older than %s days (before %s): %s", days, cutoff.isoformat(), counts)
    return counts
