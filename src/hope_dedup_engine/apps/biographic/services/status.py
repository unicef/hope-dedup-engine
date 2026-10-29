"""Mirroring a set's decision into Elasticsearch.

Postgres decides, Elasticsearch follows. A decision marks the set
`search_sync_pending`; `sync` clears it once the documents carry the matching
status, and `reconcile` catches up every set whose sync never happened, so a run
always searches against the population as Postgres knows it.
"""

import logging
from typing import Final

from elasticsearch import NotFoundError

from hope_dedup_engine.apps.biographic.models import BiographicGroup, BiographicSet
from hope_dedup_engine.apps.biographic.protocols import BiographicSearch

logger = logging.getLogger(__name__)

STATUS_PENDING: Final[str] = "pending"
STATUS_APPROVED: Final[str] = "approved"
STATUS_REJECTED: Final[str] = "rejected"

# What a set's documents must say when it is put back in the index. Only sets that
# were indexed and are still alive have documents to restore.
REBUILD_STATUS: Final[dict[str, str]] = {
    BiographicSet.State.APPROVED: STATUS_APPROVED,
    BiographicSet.State.INDEXED: STATUS_PENDING,
    BiographicSet.State.DEDUPLICATING: STATUS_PENDING,
    BiographicSet.State.DEDUPLICATED: STATUS_PENDING,
}

# Only approved documents are ever searched again. A rejected or canceled set is
# `rejected` in the index until the daily cleanup deletes it.
DOCUMENT_STATUS: Final[dict[str, str]] = {
    BiographicSet.State.APPROVED: STATUS_APPROVED,
    BiographicSet.State.REJECTED: STATUS_REJECTED,
    BiographicSet.State.CANCELED: STATUS_REJECTED,
}


def sync(dataset: BiographicSet, search: BiographicSearch) -> int:
    """Push the set's decision to its documents and clear the pending flag.

    Returns the number of documents updated. A set without a decision has nothing
    to push, and the flag is left alone. So is it when the index is missing: that
    can be a program never indexed, or an index lost and later restored from an
    older snapshot. Either way the flag stays, and `reconcile` retries once the
    next run has made sure the index exists.
    """
    status = DOCUMENT_STATUS.get(dataset.state)
    if status is None:
        logger.warning("Biographic set %s is '%s': no status to sync.", dataset.pk, dataset.state)
        return 0

    group = dataset.group
    try:
        updated = search.set_status(group.business_area, group.program_code, dataset.pk, status)
    except NotFoundError:
        logger.warning(
            "Index of %s/%s is missing: biographic set %s stays pending sync.",
            group.business_area,
            group.program_code,
            dataset.pk,
        )
        return 0
    BiographicSet.objects.filter(pk=dataset.pk).update(search_sync_pending=False)
    dataset.search_sync_pending = False
    return updated


def reconcile(group: BiographicGroup, search: BiographicSearch) -> int:
    """Sync every set in the group whose decision has not reached Elasticsearch.

    Called at the start of a run, before anything is searched, so a status task
    that was lost or is still queued cannot leave a rejected set in the population.
    Returns the number of sets synced.
    """
    pending = list(group.sets.filter(search_sync_pending=True).select_related("group"))
    for dataset in pending:
        sync(dataset, search)
    return len(pending)
