from datetime import timedelta

import pytest
from constance.test import override_config
from django.core.files.base import ContentFile
from django.utils import timezone
from freezegun import freeze_time

from hope_dedup_engine.apps.api.celery_tasks import _delete_in_batches, cleanup_redundant_data
from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding, Finding, MainJob
from hope_dedup_engine.config.celery import app as celery_app


def _backdate(deduplication_set: DeduplicationSet, *, days: int) -> None:
    DeduplicationSet.objects.filter(pk=deduplication_set.pk).update(
        updated_at=timezone.now() - timedelta(days=days),
    )


def test_cleanup_task_is_registered() -> None:
    assert "hope_dedup_engine.apps.api.celery_tasks.cleanup_redundant_data" in celery_app.tasks


def test_deletes_findings_of_old_approved_sets_and_keeps_encodings(
    deduplication_set_factory,
    finding_factory,
) -> None:
    deduplication_set = deduplication_set_factory(state=DeduplicationSet.State.APPROVED)
    finding = finding_factory(deduplication_set=deduplication_set)
    encoding_ids = list(deduplication_set.encoding_set.values_list("pk", flat=True))
    _backdate(deduplication_set, days=90)

    result = cleanup_redundant_data(retention_days=60)

    assert result["findings_sent_to_hope"] == 1
    assert result["rejected_sets"] == 0
    assert not Finding.objects.filter(pk=finding.pk).exists()
    assert Encoding.objects.filter(pk__in=encoding_ids).count() == len(encoding_ids)
    assert DeduplicationSet.objects.filter(pk=deduplication_set.pk).exists()


def test_keeps_findings_of_recently_approved_sets(deduplication_set_factory, finding_factory) -> None:
    deduplication_set = deduplication_set_factory(state=DeduplicationSet.State.APPROVED)
    finding = finding_factory(deduplication_set=deduplication_set)
    _backdate(deduplication_set, days=10)

    result = cleanup_redundant_data(retention_days=60)

    assert result["findings_sent_to_hope"] == 0
    assert Finding.objects.filter(pk=finding.pk).exists()


@freeze_time("2026-10-08 12:00:00")
def test_keeps_approved_findings_updated_exactly_at_the_cutoff(deduplication_set_factory, finding_factory) -> None:
    deduplication_set = deduplication_set_factory(state=DeduplicationSet.State.APPROVED)
    finding = finding_factory(deduplication_set=deduplication_set)
    _backdate(deduplication_set, days=60)

    cleanup_redundant_data(retention_days=60)

    assert Finding.objects.filter(pk=finding.pk).exists()


def test_deletes_old_rejected_sets_with_findings_encodings_and_files(
    deduplication_set_factory,
    deduplication_set_group_factory,
    main_job_factory,
) -> None:
    deduplication_set = deduplication_set_factory(
        group=deduplication_set_group_factory(),
        state=DeduplicationSet.State.REJECTED,
    )
    encoding = Encoding.objects.create(
        deduplication_set=deduplication_set,
        reference_pk="ref-old",
        filename=ContentFile(b"image-bytes", name="ref-old.jpg"),
    )
    storage_path = encoding.filename.name
    storage = encoding.filename.storage
    assert storage.exists(storage_path)
    finding = Finding.objects.create(
        deduplication_set=deduplication_set,
        first_encoding=encoding,
        status_code=Encoding.StatusCode.NO_FACE_DETECTED,
    )
    job = main_job_factory(deduplication_set=deduplication_set)
    _backdate(deduplication_set, days=90)

    result = cleanup_redundant_data(retention_days=60)

    assert result == {
        "findings_sent_to_hope": 0,
        "rejected_findings": 1,
        "rejected_encodings": 1,
        "rejected_sets": 1,
    }
    assert not Finding.objects.filter(pk=finding.pk).exists()
    assert not Encoding.objects.filter(pk=encoding.pk).exists()
    assert not DeduplicationSet.objects.filter(pk=deduplication_set.pk).exists()
    assert not MainJob.objects.filter(pk=job.pk).exists()
    assert not storage.exists(storage_path)


def test_keeps_recently_rejected_sets(deduplication_set_factory, finding_factory) -> None:
    deduplication_set = deduplication_set_factory(state=DeduplicationSet.State.REJECTED)
    finding = finding_factory(deduplication_set=deduplication_set)
    encoding_ids = list(deduplication_set.encoding_set.values_list("pk", flat=True))
    _backdate(deduplication_set, days=10)

    result = cleanup_redundant_data(retention_days=60)

    assert result["rejected_sets"] == 0
    assert Finding.objects.filter(pk=finding.pk).exists()
    assert Encoding.objects.filter(pk__in=encoding_ids).count() == len(encoding_ids)
    assert DeduplicationSet.objects.filter(pk=deduplication_set.pk).exists()


@pytest.mark.parametrize(
    "state",
    [
        DeduplicationSet.State.READY,
        DeduplicationSet.State.ENCODED,
        DeduplicationSet.State.DEDUPLICATED,
        DeduplicationSet.State.ENCODING_FAILED,
        DeduplicationSet.State.DEDUPLICATION_FAILED,
    ],
)
def test_leaves_sets_that_are_not_approved_or_rejected(
    deduplication_set_factory,
    deduplication_set_group_factory,
    finding_factory,
    state,
) -> None:
    deduplication_set = deduplication_set_factory(group=deduplication_set_group_factory(), state=state)
    finding = finding_factory(deduplication_set=deduplication_set)
    _backdate(deduplication_set, days=90)

    cleanup_redundant_data(retention_days=60)

    assert Finding.objects.filter(pk=finding.pk).exists()
    assert DeduplicationSet.objects.filter(pk=deduplication_set.pk).exists()


def test_keeps_findings_that_reference_encodings_from_an_old_approved_set(
    deduplication_set_group_factory,
    deduplication_set_factory,
    encoding_factory,
    finding_factory,
) -> None:
    group = deduplication_set_group_factory()
    approved = deduplication_set_factory(group=group, state=DeduplicationSet.State.APPROVED)
    approved_encoding = encoding_factory(deduplication_set=approved)
    approved_finding = finding_factory(deduplication_set=approved)
    current = deduplication_set_factory(group=group, state=DeduplicationSet.State.DEDUPLICATED)
    current_encoding = encoding_factory(deduplication_set=current)
    current_finding = finding_factory(
        deduplication_set=current,
        first_encoding=current_encoding,
        second_encoding=approved_encoding,
    )
    _backdate(approved, days=90)

    cleanup_redundant_data(retention_days=60)

    assert not Finding.objects.filter(pk=approved_finding.pk).exists()
    assert Finding.objects.filter(pk=current_finding.pk).exists()
    assert Encoding.objects.filter(pk=approved_encoding.pk).exists()
    assert Encoding.objects.filter(pk=current_encoding.pk).exists()
    assert DeduplicationSet.objects.filter(pk=approved.pk).exists()


def test_retention_days_defaults_to_constance(deduplication_set_factory, finding_factory) -> None:
    deduplication_set = deduplication_set_factory(state=DeduplicationSet.State.APPROVED)
    finding = finding_factory(deduplication_set=deduplication_set)
    _backdate(deduplication_set, days=40)

    with override_config(CLEANUP_RETENTION_DAYS=30):
        result = cleanup_redundant_data()

    assert result["findings_sent_to_hope"] == 1
    assert not Finding.objects.filter(pk=finding.pk).exists()


@pytest.mark.parametrize("retention_days", [0, -5])
def test_rejects_non_positive_retention(retention_days: int) -> None:
    with pytest.raises(ValueError, match="retention_days"):
        cleanup_redundant_data(retention_days=retention_days)


def test_delete_in_batches_removes_every_row(deduplication_set_factory, finding_factory) -> None:
    deduplication_set = deduplication_set_factory(state=DeduplicationSet.State.APPROVED)
    for _ in range(3):
        finding_factory(deduplication_set=deduplication_set)

    _delete_in_batches(Finding.objects.filter(deduplication_set=deduplication_set), batch_size=1)

    assert not Finding.objects.filter(deduplication_set=deduplication_set).exists()
