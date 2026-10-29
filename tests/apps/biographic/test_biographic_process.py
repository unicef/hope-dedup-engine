"""The processing service, step by step, against the in-memory search."""

import pytest
from testutils.biographic import FakeBiographicSearch, make_payload
from testutils.factories.biographic import (
    BiographicFindingFactory,
    BiographicJobFactory,
    BiographicRecordFactory,
    BiographicSetFactory,
)

from hope_dedup_engine.apps.api.models.jobs import GracefulJobCancellationError
from hope_dedup_engine.apps.biographic.config import resolve_config
from hope_dedup_engine.apps.biographic.exceptions import IndexMissingError
from hope_dedup_engine.apps.biographic.models import FULL_NAME_LENGTH, BiographicFinding, BiographicSet
from hope_dedup_engine.apps.biographic.services import process

pytestmark = pytest.mark.django_db

State = BiographicSet.State
Scope = BiographicFinding.Scope


@pytest.fixture
def search() -> FakeBiographicSearch:
    return FakeBiographicSearch()


@pytest.fixture
def job(no_tracking):
    return BiographicJobFactory(dataset__group__settings={"duplicate_score": 6.0, "max_hits": 100})


@pytest.fixture
def dataset(job) -> BiographicSet:
    return job.dataset


def person(dataset, reference_pk, full_name, **payload):
    return BiographicRecordFactory(
        dataset=dataset,
        reference_pk=reference_pk,
        payload={"full_name": full_name, **payload},
        full_name=full_name[:FULL_NAME_LENGTH],
    )


def approved_population(group, search, *names, dataset_id=None):
    """An earlier, approved set of `names`, already in the index."""
    population = BiographicSetFactory(group=group, state=State.APPROVED)
    records = [person(population, f"pop-{i}", name) for i, name in enumerate(names)]
    business_area, program_code = group.business_area, group.program_code
    search.ensure_index(business_area, program_code)
    search.index_records(
        business_area, program_code, dataset_id or population.pk, [process.to_payload(r) for r in records]
    )
    search.set_status(business_area, program_code, dataset_id or population.pk, "approved")
    return population


def run(job, search):
    config = resolve_config(job.dataset, job.config_overrides)
    process.prepare(job.dataset, search)
    indexed = process.index(job.dataset, search, job)
    stats = process.deduplicate(job.dataset, config, search, job)
    return indexed, stats


# --- prepare ------------------------------------------------------------------


def test_prepare_clears_the_sets_earlier_findings_only(dataset, search):
    BiographicFindingFactory(record__dataset=dataset)
    other = BiographicFindingFactory()

    process.prepare(dataset, search)

    assert not BiographicFinding.objects.filter(dataset=dataset).exists()
    assert BiographicFinding.objects.filter(pk=other.pk).exists()


def test_prepare_creates_the_index_and_reconciles_pending_decisions(dataset, search):
    group = dataset.group
    rejected = BiographicSetFactory(group=group, state=State.REJECTED, search_sync_pending=True)
    other_program = BiographicSetFactory(state=State.REJECTED, search_sync_pending=True)

    process.prepare(dataset, search)

    assert ("ensure_index", group.business_area, group.program_code) in search.calls
    assert ("set_status", rejected.pk, "rejected") in search.calls
    rejected.refresh_from_db()
    other_program.refresh_from_db()
    assert not rejected.search_sync_pending
    assert other_program.search_sync_pending


def test_prepare_refuses_to_recreate_the_index_of_a_program_with_approved_sets(dataset, search):
    """An empty index would be searched as if the approved population were empty."""
    BiographicSetFactory(group=dataset.group, state=State.APPROVED)
    BiographicFindingFactory(record__dataset=dataset)

    with pytest.raises(IndexMissingError):
        process.prepare(dataset, search)

    assert not any(call[0] == "ensure_index" for call in search.calls)
    assert BiographicFinding.objects.filter(dataset=dataset).exists()


def test_prepare_runs_when_the_index_of_a_program_with_approved_sets_exists(dataset, search):
    approved_population(dataset.group, search, "Maria Gonzalez")

    process.prepare(dataset, search)


@pytest.mark.parametrize("state", [State.REJECTED, State.CANCELED, State.FAILED])
def test_prepare_creates_the_index_when_no_set_of_the_program_is_approved(dataset, search, state):
    BiographicSetFactory(group=dataset.group, state=state)

    process.prepare(dataset, search)

    assert ("ensure_index", dataset.group.business_area, dataset.group.program_code) in search.calls


# --- prepare_search -----------------------------------------------------------


def test_prepare_search_keeps_the_index_and_drops_the_sets_findings(dataset, search):
    group = dataset.group
    search.ensure_index(group.business_area, group.program_code)
    BiographicFindingFactory(record__dataset=dataset)

    process.prepare_search(dataset, search)

    assert not BiographicFinding.objects.filter(dataset=dataset).exists()
    assert not any(call[0] == "ensure_index" for call in search.calls[1:])


def test_prepare_search_reconciles_pending_decisions(dataset, search):
    group = dataset.group
    search.ensure_index(group.business_area, group.program_code)
    rejected = BiographicSetFactory(group=group, state=State.REJECTED, search_sync_pending=True)

    process.prepare_search(dataset, search)

    rejected.refresh_from_db()
    assert not rejected.search_sync_pending


def test_prepare_search_refuses_when_the_index_is_gone(dataset, search):
    """The set was indexed, so a missing index has lost its documents."""
    BiographicFindingFactory(record__dataset=dataset)

    with pytest.raises(IndexMissingError):
        process.prepare_search(dataset, search)

    assert BiographicFinding.objects.filter(dataset=dataset).exists()


# --- rebuild ------------------------------------------------------------------


def statuses(search, group):
    docs = search.documents(group.business_area, group.program_code)
    return {key: doc.status for key, doc in docs.items()}


def test_rebuild_restores_each_set_with_the_status_postgres_gives_it(search):
    group = BiographicSetFactory().group
    approved = BiographicSetFactory(group=group, state=State.APPROVED)
    awaiting = BiographicSetFactory(group=group, state=State.DEDUPLICATED)
    person(approved, "a", "Ana Silva")
    person(awaiting, "b", "Bo Berg")

    written = process.rebuild(group, search)

    assert written == {approved.pk: 1, awaiting.pk: 1}
    assert statuses(search, group) == {f"{approved.pk}:a": "approved", f"{awaiting.pk}:b": "pending"}


@pytest.mark.parametrize("state", [State.PENDING, State.FAILED, State.REJECTED, State.CANCELED, State.INDEXING])
def test_rebuild_leaves_sets_with_nothing_to_restore(search, state):
    group = BiographicSetFactory().group
    person(BiographicSetFactory(group=group, state=state), "a", "Ana Silva")

    assert process.rebuild(group, search) == {}
    assert statuses(search, group) == {}


def test_rebuild_creates_a_missing_index(search):
    group = BiographicSetFactory().group
    assert not search.index_exists(group.business_area, group.program_code)

    process.rebuild(group, search)

    assert search.index_exists(group.business_area, group.program_code)


def test_rebuild_never_touches_documents_that_are_not_ours(search):
    """HOPE fills program indexes with `dataset_id` 0 documents Postgres does not have."""
    group = BiographicSetFactory().group
    approved = BiographicSetFactory(group=group, state=State.APPROVED)
    person(approved, "a", "Ana Silva")
    search.ensure_index(group.business_area, group.program_code)
    search.index_records(group.business_area, group.program_code, 0, [make_payload("h", full_name="Hope")])
    search.set_status(group.business_area, group.program_code, 0, "approved")

    process.rebuild(group, search)

    assert statuses(search, group) == {"0:h": "approved", f"{approved.pk}:a": "approved"}
    assert ("delete_by_status", "rejected") not in search.calls


def test_rebuild_twice_does_not_duplicate_documents(search):
    group = BiographicSetFactory().group
    approved = BiographicSetFactory(group=group, state=State.APPROVED)
    person(approved, "a", "Ana Silva")

    process.rebuild(group, search)
    process.rebuild(group, search)

    assert statuses(search, group) == {f"{approved.pk}:a": "approved"}


def test_rebuild_of_one_set_leaves_the_others_alone(search):
    group = BiographicSetFactory().group
    first = BiographicSetFactory(group=group, state=State.APPROVED)
    second = BiographicSetFactory(group=group, state=State.APPROVED)
    person(first, "a", "Ana Silva")
    person(second, "b", "Bo Berg")

    assert process.rebuild(group, search, second) == {second.pk: 1}
    assert statuses(search, group) == {f"{second.pk}:b": "approved"}


def test_rebuild_applies_a_decision_that_never_reached_the_index(search):
    group = BiographicSetFactory().group
    awaiting = BiographicSetFactory(group=group, state=State.DEDUPLICATED)
    rejected = BiographicSetFactory(group=group, state=State.REJECTED, search_sync_pending=True)
    person(awaiting, "a", "Ana Silva")
    search.ensure_index(group.business_area, group.program_code)
    search.index_records(group.business_area, group.program_code, rejected.pk, [make_payload("r")])

    process.rebuild(group, search)

    assert statuses(search, group) == {f"{awaiting.pk}:a": "pending", f"{rejected.pk}:r": "rejected"}
    rejected.refresh_from_db()
    assert not rejected.search_sync_pending


# --- index --------------------------------------------------------------------


def test_index_sends_every_record_as_a_payload_and_refreshes(dataset, search, job):
    person(dataset, "a", "Ana Silva", birth_date="1990-01-01")
    person(dataset, "b", "Bo Chen")
    search.ensure_index(dataset.group.business_area, dataset.group.program_code)

    indexed = process.index(dataset, search, job)

    assert indexed == 2
    documents = search.documents(dataset.group.business_area, dataset.group.program_code)
    assert set(documents) == {f"{dataset.pk}:a", f"{dataset.pk}:b"}
    assert documents[f"{dataset.pk}:a"].payload.birth_date == "1990-01-01"
    assert documents[f"{dataset.pk}:a"].status == "pending"
    assert search.calls[-1] == ("refresh",)


def test_index_works_in_chunks_and_checks_for_cancellation_between_them(dataset, search, job, mocker):
    mocker.patch.object(process, "INDEX_CHUNK_SIZE", 2)
    BiographicRecordFactory.create_batch(5, dataset=dataset)
    ensure = mocker.patch.object(job, "ensure_not_cancelled")

    process.index(dataset, search, job)

    assert [c[2] for c in search.calls if c[0] == "index_records"] == [2, 2, 1]
    assert ensure.call_count == 3


def test_index_stops_when_cancellation_is_requested(dataset, search, job, mocker):
    BiographicRecordFactory(dataset=dataset)
    mocker.patch.object(job, "ensure_not_cancelled", side_effect=GracefulJobCancellationError("stop"))

    with pytest.raises(GracefulJobCancellationError):
        process.index(dataset, search, job)
    assert not [c for c in search.calls if c[0] == "index_records"]


# --- deduplicate --------------------------------------------------------------


def test_deduplicate_splits_findings_by_scope(job, dataset, search):
    approved_population(dataset.group, search, "Ana Silva")
    ana = person(dataset, "a", "Ana Silva")
    ana_again = person(dataset, "b", "ana silva")
    person(dataset, "c", "Bo Chen")

    indexed, stats = run(job, search)

    assert indexed == 3
    assert stats.findings_created == 4
    assert stats.records_truncated == 0
    pairs = {
        (f.record.reference_pk, f.matched_reference_pk, f.scope)
        for f in BiographicFinding.objects.filter(dataset=dataset).select_related("record")
    }
    assert pairs == {
        ("a", "b", Scope.BATCH),
        ("b", "a", Scope.BATCH),
        ("a", "pop-0", Scope.POPULATION),
        ("b", "pop-0", Scope.POPULATION),
    }
    finding = BiographicFinding.objects.get(record=ana, matched_reference_pk="pop-0")
    assert finding.dataset == dataset
    assert finding.matched_full_name == "Ana Silva"
    assert finding.score == search.match_score
    assert finding.proximity_to_score == search.match_score - 6.0
    assert finding.config == resolve_config(dataset).as_dict()
    assert BiographicFinding.objects.filter(record=ana_again).count() == 2


def test_deduplicate_honours_the_run_overrides(search, no_tracking):
    job = BiographicJobFactory(config_overrides={"duplicate_score": 12.0})
    person(job.dataset, "a", "Ana Silva")
    person(job.dataset, "b", "Ana Silva")

    _, stats = run(job, search)

    # The fake scores 10: below the overridden threshold, so nothing matches.
    assert stats.findings_created == 0
    assert search.calls[-1] == ("search_many", job.dataset.pk, 2)


def test_deduplicate_keeps_the_best_hit_per_matched_person_and_scope(job, dataset, search):
    """The same person approved twice is two documents, and one finding."""
    group = dataset.group
    approved_population(group, search, "Ana Silva")
    first = BiographicSet.objects.filter(group=group, state=State.APPROVED).get()
    search.index_records(
        group.business_area,
        group.program_code,
        first.pk + 1000,
        [process.to_payload(r) for r in first.records.all()],
    )
    search.set_status(group.business_area, group.program_code, first.pk + 1000, "approved")
    person(dataset, "a", "Ana Silva")

    _, stats = run(job, search)

    assert stats.findings_created == 1
    assert BiographicFinding.objects.get(dataset=dataset).matched_reference_pk == "pop-0"


def test_documents_migrated_from_hope_count_as_population(job, dataset, search):
    """`dataset_id = 0` is reserved for HOPE's existing population."""
    approved_population(dataset.group, search, "Ana Silva", dataset_id=0)
    person(dataset, "a", "Ana Silva")

    run(job, search)

    finding = BiographicFinding.objects.get(dataset=dataset)
    assert (finding.scope, finding.matched_reference_pk) == (Scope.POPULATION, "pop-0")


def test_deduplicate_counts_records_that_hit_the_hits_limit(search, no_tracking):
    job = BiographicJobFactory(config_overrides={"max_hits": 2})
    for i in range(4):
        person(job.dataset, f"r{i}", "Ana Silva")

    _, stats = run(job, search)

    assert stats.findings_created == 8
    assert stats.records_truncated == 4


def test_deduplicate_truncates_an_overlong_matched_name(job, dataset, search):
    long_name = "A" * (FULL_NAME_LENGTH + 20)
    approved_population(dataset.group, search, long_name)
    person(dataset, "a", long_name)

    run(job, search)

    assert len(BiographicFinding.objects.get(dataset=dataset).matched_full_name) == FULL_NAME_LENGTH


def test_deduplicate_reports_progress_per_chunk(job, dataset, search, mocker):
    mocker.patch.object(process, "SEARCH_CHUNK_SIZE", 2)
    BiographicRecordFactory.create_batch(5, dataset=dataset)
    total = mocker.patch.object(job, "set_total")
    progress = mocker.patch.object(job, "set_progress")

    run(job, search)

    total.assert_called_once_with(5)
    assert [c.args[0] for c in progress.call_args_list] == [2, 4, 5]
    assert [c[2] for c in search.calls if c[0] == "search_many"] == [2, 2, 1]


def test_deduplicate_stops_between_chunks_when_cancelled(job, dataset, search, mocker):
    mocker.patch.object(process, "SEARCH_CHUNK_SIZE", 1)
    person(dataset, "a", "Ana Silva")
    person(dataset, "b", "Ana Silva")
    config = resolve_config(dataset)
    process.prepare(dataset, search)
    process.index(dataset, search, job)
    mocker.patch.object(job, "ensure_not_cancelled", side_effect=[None, GracefulJobCancellationError("stop")])

    with pytest.raises(GracefulJobCancellationError):
        process.deduplicate(dataset, config, search, job)

    # The first chunk's findings are in; the retry's `prepare` clears them.
    assert BiographicFinding.objects.filter(dataset=dataset).count() == 1


def test_a_rerun_does_not_duplicate_findings(job, dataset, search):
    person(dataset, "a", "Ana Silva")
    person(dataset, "b", "Ana Silva")

    run(job, search)
    run(job, search)

    assert BiographicFinding.objects.filter(dataset=dataset).count() == 2


def test_other_pending_sets_are_not_candidates(job, dataset, search):
    """Two batches in flight must not see each other."""
    other = BiographicSetFactory(group=dataset.group, state=State.FAILED)
    other_record = person(other, "x", "Ana Silva")
    search.ensure_index(dataset.group.business_area, dataset.group.program_code)
    search.index_records(
        dataset.group.business_area, dataset.group.program_code, other.pk, [process.to_payload(other_record)]
    )
    person(dataset, "a", "Ana Silva")

    _, stats = run(job, search)

    assert stats.findings_created == 0
