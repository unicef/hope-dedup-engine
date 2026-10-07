"""The interface the biographic service calls, and the search library implements.

A `Protocol` rather than a base class: `ElasticsearchBiographicSearch` satisfies it
structurally, without inheriting, and so does any in-memory fake the service wants
to test against. It lives here, above both, so that annotating a service attribute
does not drag the Elasticsearch adapter into the import graph.

Frozen: changing anything here needs the agreement of every assignee on the
biographic deduplication issues, because both sides of the split depend on it.

Settled with the interface:

* a ``BiographicGroup`` is one business area plus one program. It owns the config,
  the processing lock, and maps 1:1 onto an Elasticsearch index
* ``BiographicRecord`` stores the scoreable fields as a single JSON ``payload``;
  ``PAYLOAD_FIELDS`` is the only place that list exists
* index name: ``biographic_{business_area}_{program_code}``
* Elasticsearch document id: ``{dataset_id}:{reference_pk}``
* status values: ``pending`` / ``approved`` / ``rejected``
* one search covers both sides at once: the rest of the caller's dataset, still
  pending, plus the approved population. Each hit says which it was, so
  within-batch duplicates are a filter on the result, not a second search
* classification lives in the service, not in the search library. The library
  returns scored hits and has no opinion on what a duplicate is
"""

from typing import Protocol

from hope_dedup_engine.apps.biographic.schemas import BiographicPayload, Hit


class BiographicSearch(Protocol):
    def ensure_index(self, business_area: str, program_code: str) -> str: ...

    def index_records(
        self,
        business_area: str,
        program_code: str,
        dataset_id: int,
        records: list[BiographicPayload],
    ) -> int: ...

    def refresh(self, business_area: str, program_code: str) -> None: ...

    def search(  # noqa: PLR0913, PLR0917 - the contract is frozen
        self,
        business_area: str,
        program_code: str,
        payload: BiographicPayload,
        min_score: float,
        dataset_id: int,
        size: int = 100,
    ) -> list[Hit]: ...

    def set_status(
        self,
        business_area: str,
        program_code: str,
        dataset_id: int,
        status: str,  # "approved" | "rejected"
    ) -> int: ...

    def delete_by_status(self, status: str) -> dict[str, int]: ...
