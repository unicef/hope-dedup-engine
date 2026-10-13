"""Mirroring decisions into the index: `services.status`."""

import pytest
from testutils.biographic import FakeBiographicSearch, make_payload
from testutils.factories.biographic import BiographicSetFactory

from hope_dedup_engine.apps.biographic.models import BiographicSet
from hope_dedup_engine.apps.biographic.services import status

pytestmark = pytest.mark.django_db

State = BiographicSet.State


@pytest.fixture
def search() -> FakeBiographicSearch:
    return FakeBiographicSearch()


def indexed(search, dataset, *reference_pks):
    group = dataset.group
    search.ensure_index(group.business_area, group.program_code)
    search.index_records(
        group.business_area, group.program_code, dataset.pk, [make_payload(pk) for pk in reference_pks]
    )


def statuses(search, dataset):
    return {doc.payload.reference_pk: doc.status for doc in search.documents(**group_key(dataset)).values()}


def group_key(dataset):
    return {"business_area": dataset.group.business_area, "program_code": dataset.group.program_code}


@pytest.mark.parametrize(
    ("state", "expected"),
    [(State.APPROVED, "approved"), (State.REJECTED, "rejected"), (State.CANCELED, "rejected")],
)
def test_sync_maps_the_decision_onto_the_documents(search, state, expected):
    dataset = BiographicSetFactory(state=state, search_sync_pending=True)
    indexed(search, dataset, "a", "b")

    updated = status.sync(dataset, search)

    assert updated == 2
    assert statuses(search, dataset) == {"a": expected, "b": expected}
    dataset.refresh_from_db()
    assert not dataset.search_sync_pending


def test_sync_leaves_other_sets_alone(search):
    dataset = BiographicSetFactory(state=State.APPROVED, search_sync_pending=True)
    other = BiographicSetFactory(group=dataset.group, state=State.PENDING)
    indexed(search, dataset, "a")
    indexed(search, other, "x")

    status.sync(dataset, search)

    assert statuses(search, dataset) == {"a": "approved", "x": "pending"}


@pytest.mark.parametrize("state", [s for s in State if s not in status.DOCUMENT_STATUS])
def test_sync_without_a_decision_does_nothing(search, state, mocker):
    dataset = BiographicSetFactory(state=state, search_sync_pending=True)
    logger = mocker.patch.object(status, "logger")

    assert status.sync(dataset, search) == 0

    assert not search.calls
    dataset.refresh_from_db()
    assert dataset.search_sync_pending
    logger.warning.assert_called_once()


def test_sync_with_no_index_just_clears_the_flag(search):
    """Nothing of the program was ever indexed, so there is nothing to update."""
    dataset = BiographicSetFactory(state=State.REJECTED, search_sync_pending=True)

    assert status.sync(dataset, search) == 0

    dataset.refresh_from_db()
    assert not dataset.search_sync_pending


def test_reconcile_syncs_every_pending_set_of_the_group_only(search):
    group_set = BiographicSetFactory(state=State.APPROVED, search_sync_pending=True)
    group = group_set.group
    second = BiographicSetFactory(group=group, state=State.CANCELED, search_sync_pending=True)
    done = BiographicSetFactory(group=group, state=State.APPROVED, search_sync_pending=False)
    elsewhere = BiographicSetFactory(state=State.APPROVED, search_sync_pending=True)
    indexed(search, group_set, "a")
    indexed(search, second, "b")
    indexed(search, done, "c")

    synced = status.reconcile(group, search)

    assert synced == 2
    assert statuses(search, group_set) == {"a": "approved", "b": "rejected", "c": "pending"}
    elsewhere.refresh_from_db()
    assert elsewhere.search_sync_pending
    assert not group.sets.filter(search_sync_pending=True).exists()
