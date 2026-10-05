"""Shared contract between the biographic orchestration layer and the search library.

Frozen: changing anything here needs the agreement of every assignee on the
biographic deduplication issues, because both sides of the split depend on it.

Settled with the contract:

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
* identity documents are not part of the payload. Matching them is exact, not
  fuzzy, so it belongs in Postgres, which is where HOPE does it too
  (``HardDocumentDeduplication``, a separate task from the Elasticsearch pass)
"""

from dataclasses import dataclass
from typing import Protocol

# The authoritative list of scoreable fields. The API serializer validates
# against this, and the ES mapping mirrors it. Neither may drift from it.
PAYLOAD_FIELDS = (
    "given_name",
    "family_name",
    "full_name",
    "middle_name",
    "birth_date",
    "phone_no",
    "phone_no_alternative",
    "sex",
    "relationship",
)

PAYLOAD_VERSION = 1


@dataclass(frozen=True)
class BiographicPayload:
    """One person's scoreable fields.

    Mirrors the subset of HOPE's IndividualDocument that actually contributes to a
    similarity score.
    """

    reference_pk: str
    given_name: str | None
    family_name: str | None
    full_name: str | None
    middle_name: str | None
    birth_date: str | None  # ISO 8601
    phone_no: str | None
    phone_no_alternative: str | None
    sex: str | None
    relationship: str | None


@dataclass(frozen=True)
class Hit:
    """A scored match.

    Carries no business meaning - the service decides whether this is a duplicate.
    `dataset_id` and `status` say where the match came from, so a caller that
    wants only within-batch duplicates filters on them rather than searching again.
    """

    reference_pk: str
    score: float
    dataset_id: int
    status: str
    full_name: str | None
    birth_date: str | None


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
