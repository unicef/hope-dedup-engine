"""The work of one run: index the set, score it, store the findings.

Three steps, called in order by the processing task, which owns the state
changes, notifications and the log in between. Each step takes the search
backend as an argument, so the tests drive them with an in-memory fake.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final

from hope_dedup_engine.apps.biographic.config import BiographicConfig
from hope_dedup_engine.apps.biographic.models import (
    BULK_CREATE_BATCH_SIZE,
    FULL_NAME_LENGTH,
    BiographicFinding,
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


def prepare(dataset: BiographicSet, search: BiographicSearch) -> None:
    """Start clean: drop this set's findings, make sure the index exists and is current.

    A retry after a failure must not keep half a result. Reconciling first means
    every decision in the program is in the index before anything is searched,
    including one whose status task was lost.
    """
    BiographicFinding.objects.filter(dataset=dataset).delete()
    group = dataset.group
    search.ensure_index(group.business_area, group.program_code)
    status.reconcile(group, search)


def index(dataset: BiographicSet, search: BiographicSearch, job: BiographicJob) -> int:
    """Index the set's records as `pending` and make them searchable. Returns the count."""
    group = dataset.group
    indexed = 0
    for chunk in _chunks(dataset, INDEX_CHUNK_SIZE):
        job.ensure_not_cancelled()
        indexed += search.index_records(
            group.business_area, group.program_code, dataset.pk, [to_payload(record) for record in chunk]
        )
    search.refresh(group.business_area, group.program_code)
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
            group.business_area,
            group.program_code,
            [to_payload(record) for record in chunk],
            min_score=config.duplicate_score,
            dataset_id=dataset.pk,
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
        scope = BiographicFinding.Scope.BATCH if hit.dataset_id == dataset.pk else BiographicFinding.Scope.POPULATION
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
