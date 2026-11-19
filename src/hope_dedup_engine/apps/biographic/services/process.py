"""The work of one run: index the set, score it, store the findings.

Three steps, called in order by the processing task, which owns the state
changes, notifications and the log in between. Each step takes the search
backend as an argument, so the tests drive them with an in-memory fake.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final

from hope_dedup_engine.apps.biographic.config import BiographicConfig
from hope_dedup_engine.apps.biographic.exceptions import IndexMissingError, IndexRebuildRequiredError
from hope_dedup_engine.apps.biographic.models import (
    BULK_CREATE_BATCH_SIZE,
    FULL_NAME_LENGTH,
    BiographicFinding,
    BiographicGroup,
    BiographicJob,
    BiographicRecord,
    BiographicSet,
)
from hope_dedup_engine.apps.biographic.protocols import BiographicSearch
from hope_dedup_engine.apps.biographic.schemas import PAYLOAD_FIELDS, BiographicPayload, Hit
from hope_dedup_engine.apps.biographic.services import status

# Records per Elasticsearch bulk request. HOPE's chunk size.
INDEX_CHUNK_SIZE: Final[int] = 2_000
# Records per msearch, and the unit of progress and cancellation checks.
SEARCH_CHUNK_SIZE: Final[int] = 200


@dataclass(frozen=True)
class DeduplicationStats:
    findings_created: int
    # Records whose hits hit `max_hits`: there may have been more matches than stored.
    records_truncated: int


def to_payload(record: BiographicRecord) -> BiographicPayload:
    return BiographicPayload(reference_pk=record.reference_pk, **{f: record.payload.get(f) for f in PAYLOAD_FIELDS})


def _chunks(dataset: BiographicSet, size: int) -> Iterator[list[BiographicRecord]]:
    """Yield the set's records in pk order, `size` at a time.

    Keyset pagination rather than `.iterator()`: a server-side cursor would stay
    open across every Elasticsearch call of the run, and an exception mid-run
    would leave it dangling in the transaction.
    """
    last_pk = 0
    while True:
        chunk = list(dataset.records.filter(pk__gt=last_pk).order_by("pk").only("reference_pk", "payload")[:size])
        if not chunk:
            return
        yield chunk
        last_pk = chunk[-1].pk


def _check_rebuild_complete(group: BiographicGroup) -> None:
    """Refuse to use an index whose full rebuild has not finished."""
    if BiographicGroup.objects.filter(pk=group.pk, index_rebuild_required=True).exists():
        raise IndexRebuildRequiredError(
            f"The index of {group.business_area}/{group.program_code} requires a full rebuild. "
            "Use Rebuild index on the biographic group."
        )


def _check_population_index(group: BiographicGroup, search: BiographicSearch) -> None:
    """Refuse to run with an unfinished full rebuild or a missing approved population index.

    `ensure_index` would quietly create an empty one, and the run would then search
    an incomplete population and find nothing. A program with no approved set and
    no unfinished rebuild can create the index on its first run as usual.

    An unfinished full rebuild blocks processing even when the index exists.
    """
    _check_rebuild_complete(group)
    if search.index_exists(group.pk):
        return
    if group.sets.filter(state=BiographicSet.State.APPROVED).exists():
        raise IndexMissingError(
            f"The index of {group.business_area}/{group.program_code} is missing, but the program "
            "has approved sets. It has to be rebuilt before another run can search the population."
        )


def prepare(dataset: BiographicSet, search: BiographicSearch) -> None:
    """Start clean: drop this set's findings, make sure the index exists and is current.

    A retry after a failure must not keep half a result. Reconciling first means
    every decision in the program is in the index before anything is searched,
    including one whose status task was lost.
    """
    group = dataset.group
    _check_population_index(group, search)
    BiographicFinding.objects.filter(dataset=dataset).delete()
    search.ensure_index(group.pk)
    status.reconcile(group, search)


def prepare_search(dataset: BiographicSet, search: BiographicSearch) -> None:
    """Start a search of a set that is already indexed: drop its findings, bring statuses up to date.

    Unlike `prepare` it never creates the index. The set's own documents were
    indexed by an earlier run, so an index that is gone has lost them: searching
    would find nothing, and a rebuild has to put them back first.
    An unfinished full rebuild also blocks the search before any findings are removed.
    """
    group = dataset.group
    _check_rebuild_complete(group)
    if not search.index_exists(group.pk):
        raise IndexMissingError(
            f"The index of {group.business_area}/{group.program_code} is missing, so set {dataset.pk} "
            "is no longer indexed. Rebuild the index before searching."
        )
    BiographicFinding.objects.filter(dataset=dataset).delete()
    status.reconcile(group, search)


def index(dataset: BiographicSet, search: BiographicSearch, job: BiographicJob) -> int:
    """Index the set's records as `pending` and make them searchable. Returns the count."""
    group = dataset.group
    indexed = 0
    for chunk in _chunks(dataset, INDEX_CHUNK_SIZE):
        job.ensure_not_cancelled()
        indexed += search.index_records(
            group.pk, group.business_area, group.program_code, str(dataset.pk), [to_payload(record) for record in chunk]
        )
    search.refresh(group.pk)
    return indexed


def deduplicate(
    dataset: BiographicSet, config: BiographicConfig, search: BiographicSearch, job: BiographicJob
) -> DeduplicationStats:
    """Score every record and store one finding per matched person and scope."""
    group = dataset.group
    config_snapshot = config.as_dict()
    findings_created = 0
    records_truncated = 0
    processed = 0

    job.set_total(dataset.records.count())
    for chunk in _chunks(dataset, SEARCH_CHUNK_SIZE):
        job.ensure_not_cancelled()
        hits_per_record = search.search_many(
            group.pk,
            [to_payload(record) for record in chunk],
            min_score=config.duplicate_score,
            dataset_id=str(dataset.pk),
            size=config.max_hits,
        )
        findings: list[BiographicFinding] = []
        for record, hits in zip(chunk, hits_per_record, strict=True):
            if len(hits) >= config.max_hits:
                records_truncated += 1
            findings.extend(_findings_for(dataset, record, hits, config, config_snapshot))
        BiographicFinding.objects.bulk_create(findings, batch_size=BULK_CREATE_BATCH_SIZE)
        findings_created += len(findings)
        processed += len(chunk)
        job.set_progress(processed)

    return DeduplicationStats(findings_created=findings_created, records_truncated=records_truncated)


def _findings_for(
    dataset: BiographicSet,
    record: BiographicRecord,
    hits: list[Hit],
    config: BiographicConfig,
    config_snapshot: dict[str, object],
) -> list[BiographicFinding]:
    """Turn one record's hits into findings, the best hit per person and scope.

    A person sent in two approved sets is two documents sharing a `reference_pk`,
    and both can come back for one search. `unique_biographic_finding` allows one
    row per (record, matched person, scope), so only the best-scoring hit is kept.
    Hits arrive best first, so the first one seen wins.
    """
    seen: set[tuple[str, str]] = set()
    findings = []
    for hit in hits:
        in_batch = hit.dataset_id == str(dataset.pk)
        scope = BiographicFinding.Scope.BATCH if in_batch else BiographicFinding.Scope.POPULATION
        key = (hit.reference_pk, scope)
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            BiographicFinding(
                dataset=dataset,
                record=record,
                matched_reference_pk=hit.reference_pk,
                matched_full_name=(hit.full_name or "")[:FULL_NAME_LENGTH],
                matched_birth_date=hit.birth_date,
                score=hit.score,
                proximity_to_score=hit.score - config.duplicate_score,
                scope=scope,
                config=config_snapshot,
            )
        )
    return findings


def rebuild(group: BiographicGroup, search: BiographicSearch, dataset: BiographicSet | None = None) -> dict[str, int]:
    """Restore the group's indexed sets from the records kept in Postgres.

    Additive on purpose: a full rebuild creates the group's index if missing,
    but an existing index is never deleted or emptied. Only this group's sets
    are restored; a newly registered group has its own index and cannot inherit
    a deleted group's population. Document ids are `{dataset_id}:{reference_pk}`,
    so existing documents are overwritten rather than duplicated.

    Each set is restored with the status Postgres gives it: approved sets as
    `approved`, indexed and deduplicating/deduplicated sets as `pending`.
    Rejected, canceled, pending, indexing and failed sets are not restored.
    Pass `dataset` to restore only that one; this requires an existing index
    with no unfinished full rebuild. Returns documents written per set.

    A full rebuild marks the index as requiring recovery before any index work.
    The marker is cleared only after all sets are written, the index is refreshed
    and pending status changes are reconciled. A failure leaves processing blocked
    until a full rebuild succeeds.
    """
    business_area, program_code = group.business_area, group.program_code
    if dataset is None:
        group.index_rebuild_required = True
        group.save(update_fields=["index_rebuild_required"])
        search.ensure_index(group.pk)
    else:
        _check_rebuild_complete(group)
        if not search.index_exists(group.pk):
            raise IndexMissingError(
                f"The index of {business_area}/{program_code} is missing. "
                "Use Rebuild index on the biographic group before rebuilding individual sets."
            )

    sets = group.sets.filter(state__in=list(status.REBUILD_STATUS))
    if dataset is not None:
        sets = sets.filter(pk=dataset.pk)

    written: dict[str, int] = {}
    for target in sets.order_by("created_at", "pk"):
        document_status = status.REBUILD_STATUS[target.state]
        written[str(target.pk)] = sum(
            search.index_records(
                group.pk,
                business_area,
                program_code,
                str(target.pk),
                [to_payload(record) for record in chunk],
                document_status,
            )
            for chunk in _chunks(target, INDEX_CHUNK_SIZE)
        )
    search.refresh(group.pk)
    # A decision that never reached the index is applied on top of what was restored.
    status.reconcile(group, search)
    if dataset is None:
        group.index_rebuild_required = False
        group.save(update_fields=["index_rebuild_required"])
    return written
