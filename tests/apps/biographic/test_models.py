from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from hope_dedup_engine.apps.biographic import contracts
from hope_dedup_engine.apps.biographic.contracts import (
    BIRTH_DATE_FIELD,
    FULL_NAME_FIELD,
    IDENTITIES_FIELD,
    PAYLOAD_FIELDS,
    PAYLOAD_VERSION,
    DocumentStatus,
    MatchScope,
    document_id,
    index_name,
)
from hope_dedup_engine.apps.biographic.models import (
    FULL_NAME_LENGTH,
    BiographicGroup,
    BiographicRecord,
    BiographicSet,
)
from testutils.factories.biographic import BiographicGroupFactory, BiographicRecordFactory, BiographicSetFactory

pytestmark = pytest.mark.django_db


def test_contract_names_documents_and_statuses() -> None:
    assert index_name("afghanistan", "42") == "biographic_afghanistan_42"
    assert document_id(7, "cw-1") == "7:cw-1"
    assert PAYLOAD_VERSION == 1
    assert {item.value for item in DocumentStatus} == {"pending", "approved", "rejected"}
    assert {item.value for item in MatchScope} == {"batch", "population"}
    assert BIRTH_DATE_FIELD in PAYLOAD_FIELDS
    assert IDENTITIES_FIELD in PAYLOAD_FIELDS
    assert FULL_NAME_FIELD in PAYLOAD_FIELDS


def test_owned_modules_do_not_import_elasticsearch() -> None:
    root = Path(contracts.__file__).parent
    for path in root.rglob("*.py"):
        text = path.read_text()
        assert "import elasticsearch" not in text
        assert "from elasticsearch" not in text


def test_group_business_area_and_program_are_unique() -> None:
    BiographicGroupFactory(business_area="afghanistan", program_id="one")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BiographicGroupFactory(business_area="afghanistan", program_id="one")


def test_programs_in_one_business_area_lock_independently() -> None:
    first = BiographicGroupFactory(business_area="afghanistan", program_id="one")
    second = BiographicGroupFactory(business_area="afghanistan", program_id="two")

    assert first.acquire_processing_lock() is True
    assert second.acquire_processing_lock() is True
    assert first.acquire_processing_lock() is False

    first.release_processing_lock()
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.processing_locked is False
    assert second.processing_locked is True


def test_release_processing_lock_is_idempotent() -> None:
    group = BiographicGroupFactory()
    group.release_processing_lock()
    group.refresh_from_db()
    assert group.processing_locked is False


def test_pending_sets_may_share_a_group() -> None:
    group = BiographicGroupFactory()
    BiographicSetFactory(group=group, state=BiographicSet.State.PENDING)
    BiographicSetFactory(group=group, state=BiographicSet.State.PENDING)
    assert group.sets.count() == 2


@pytest.mark.parametrize("state", [BiographicSet.State.DEDUPLICATING, BiographicSet.State.DEDUPLICATED])
def test_only_one_in_flight_set_per_group(state: str) -> None:
    group = BiographicGroupFactory()
    BiographicSetFactory(group=group, state=state)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BiographicSetFactory(group=group, state=state)


def test_approve_path() -> None:
    dataset = BiographicSetFactory()
    dataset.set_state(BiographicSet.State.DEDUPLICATING)
    dataset.set_state(BiographicSet.State.DEDUPLICATED)
    dataset.set_state(BiographicSet.State.APPROVED)
    assert dataset.state == BiographicSet.State.APPROVED


def test_reject_path() -> None:
    dataset = BiographicSetFactory()
    dataset.set_state(BiographicSet.State.DEDUPLICATING)
    dataset.set_state(BiographicSet.State.DEDUPLICATED)
    dataset.set_state(BiographicSet.State.REJECTED)
    assert dataset.state == BiographicSet.State.REJECTED


def test_reject_after_approve_fails() -> None:
    dataset = BiographicSetFactory()
    dataset.set_state(BiographicSet.State.DEDUPLICATING)
    dataset.set_state(BiographicSet.State.DEDUPLICATED)
    dataset.set_state(BiographicSet.State.APPROVED)

    with pytest.raises(ValueError, match="Approved -> Rejected"):
        dataset.set_state(BiographicSet.State.REJECTED)

    dataset.refresh_from_db()
    assert dataset.state == BiographicSet.State.APPROVED


def _invalid_transitions() -> list[tuple[str, str]]:
    return [
        (origin, target)
        for origin in BiographicSet.State
        for target in BiographicSet.State
        if target not in BiographicSet.VALID_TRANSITIONS[origin]
    ]


@pytest.mark.parametrize(("origin", "target"), _invalid_transitions())
def test_invalid_state_transition(origin: str, target: str) -> None:
    dataset = BiographicSetFactory()
    BiographicSet.objects.filter(pk=dataset.pk).update(state=origin)
    dataset.refresh_from_db()
    with pytest.raises(ValueError, match="Invalid state transition"):
        dataset.set_state(target)


def test_unknown_state_is_rejected() -> None:
    dataset = BiographicSetFactory()
    with pytest.raises(ValueError, match="Unknown state"):
        dataset.set_state("archived")


def _complete_payload() -> dict[str, object]:
    payload: dict[str, object] = {}
    for name in PAYLOAD_FIELDS:
        if name == BIRTH_DATE_FIELD:
            payload[name] = "1990-05-15"
        elif name == IDENTITIES_FIELD:
            payload[name] = [{"number": "A123", "partner": "UNHCR"}]
        elif name == FULL_NAME_FIELD:
            payload[name] = "Maria Gonzalez"
        else:
            payload[name] = name
    return payload


def test_valid_payload_round_trips_and_populates_full_name() -> None:
    payload = _complete_payload()
    record = BiographicRecordFactory(payload=payload, full_name="")
    record.refresh_from_db()
    assert record.payload == payload
    assert record.full_name == "Maria Gonzalez"
    assert record.payload_version == PAYLOAD_VERSION


def test_full_name_column_is_truncated_without_changing_the_payload() -> None:
    payload = {"full_name": "M" * (FULL_NAME_LENGTH + 10)}
    record = BiographicRecordFactory(payload=payload)
    record.refresh_from_db()
    assert record.full_name == "M" * FULL_NAME_LENGTH
    assert record.payload["full_name"] == payload["full_name"]


def test_null_birth_date_and_empty_identities_round_trip() -> None:
    payload = {"birth_date": None, "identities": [], "given_name": None}
    record = BiographicRecordFactory(payload=payload)
    record.refresh_from_db()
    assert record.payload == payload
    assert record.full_name == ""


@pytest.mark.parametrize(
    "payload",
    [
        {"birth_date": "15/05/1990"},
        {"birth_date": "not-a-date"},
        {"birth_date": ""},
        {"not_a_field": "x"},
        {"identities": "A123"},
        {"identities": [{"number": 1, "partner": "UNHCR"}]},
        {"identities": [{"number": "A123"}]},
        {"identities": [{"number": "A123", "partner": "UNHCR", "extra": "no"}]},
        {"given_name": 1},
        [],
    ],
)
def test_save_rejects_invalid_payload(payload: object) -> None:
    dataset = BiographicSetFactory()
    record = BiographicRecord(dataset=dataset, reference_pk="cw-1", payload=payload)
    with pytest.raises(ValidationError):
        record.save()


def test_duplicate_reference_pk_in_one_dataset_is_rejected() -> None:
    record = BiographicRecordFactory(reference_pk="cw-1")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BiographicRecordFactory(dataset=record.dataset, reference_pk="cw-1")


def test_same_reference_pk_is_allowed_in_another_dataset() -> None:
    BiographicRecordFactory(reference_pk="cw-1")
    BiographicRecordFactory(reference_pk="cw-1")
    assert BiographicRecord.objects.filter(reference_pk="cw-1").count() == 2


def test_group_does_not_copy_business_area_onto_the_set() -> None:
    dataset = BiographicSetFactory()
    assert not hasattr(dataset, "business_area")
    assert not hasattr(dataset, "program_id")
    assert dataset.group.business_area
    assert BiographicGroup.objects.filter(pk=dataset.group_id).exists()
