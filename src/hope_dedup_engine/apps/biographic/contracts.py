"""Frozen biographic contract shared by the API, the search client, and the service.

Groups are scoped to one business area plus one program. Payloads are JSON.
The index name is ``biographic_{business_area}_{program_id}``. Elasticsearch
document ids are ``{dataset_id}:{reference_pk}``. Document statuses are
``pending``, ``approved``, and ``rejected``.

A stored hit is a duplicate. There is no possible-duplicate classification.
``proximity_to_score`` is ``score - duplicate_score``.

``program_id`` stores the value the caller sends. HOPE has not yet confirmed
whether that value is a program id or a program code.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol, TypedDict

PAYLOAD_VERSION: Final[int] = 1

BIRTH_DATE_FIELD: Final[str] = "birth_date"
IDENTITIES_FIELD: Final[str] = "identities"
FULL_NAME_FIELD: Final[str] = "full_name"

PAYLOAD_FIELDS: Final[tuple[str, ...]] = (
    "given_name",
    "middle_name",
    "family_name",
    FULL_NAME_FIELD,
    BIRTH_DATE_FIELD,
    "phone_no",
    "phone_no_alternative",
    "sex",
    "relationship",
    "admin1",
    "admin2",
    IDENTITIES_FIELD,
)

IDENTITY_NUMBER_FIELD: Final[str] = "number"
IDENTITY_PARTNER_FIELD: Final[str] = "partner"
IDENTITY_FIELDS: Final[tuple[str, ...]] = (IDENTITY_NUMBER_FIELD, IDENTITY_PARTNER_FIELD)


class DocumentStatus(StrEnum):
    """Lifecycle status stored on an Elasticsearch document."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MatchScope(StrEnum):
    """Where a scored hit was found."""

    BATCH = "batch"
    POPULATION = "population"


class Identity(TypedDict):
    """One identity document on a person."""

    number: str
    partner: str


class BiographicPayload(TypedDict, total=False):
    """Scoreable fields for one person. Keys are exactly ``PAYLOAD_FIELDS``."""

    given_name: str
    middle_name: str
    family_name: str
    full_name: str
    birth_date: str
    phone_no: str
    phone_no_alternative: str
    sex: str
    relationship: str
    admin1: str
    admin2: str
    identities: list[Identity]


@dataclass(frozen=True, slots=True)
class Hit:
    """One scored match. Order is highest score first."""

    reference_pk: str
    score: float
    full_name: str = ""
    birth_date: str | None = None


@dataclass(frozen=True, slots=True)
class IndexRecord:
    """One person to index. The document id is ``{dataset_id}:{reference_pk}``."""

    dataset_id: int
    reference_pk: str
    payload: BiographicPayload
    status: DocumentStatus


class BiographicSearch(Protocol):
    """Elasticsearch operations. Implementations must not be imported by the API."""

    def ensure_index(self, business_area: str, program_id: str) -> str:
        """Create the program index when missing and return its name."""

    def index_records(self, business_area: str, program_id: str, records: Sequence[IndexRecord]) -> None:
        """Bulk-index records into ``biographic_{business_area}_{program_id}``."""

    def refresh(self, business_area: str, program_id: str) -> None:
        """Refresh the program index."""

    def search(  # noqa: PLR0913
        self,
        business_area: str,
        program_id: str,
        payload: BiographicPayload,
        *,
        scope: MatchScope,
        min_score: float,
        exclude_document_id: str | None = None,
        size: int = 100,
    ) -> Sequence[Hit]:
        """Return scored hits for one person, highest score first."""

    def set_status(self, business_area: str, program_id: str, dataset_id: int, status: DocumentStatus) -> None:
        """Set the lifecycle status on every document in one dataset."""

    def delete_by_status(self, business_area: str, program_id: str, status: DocumentStatus) -> int:
        """Delete documents with ``status`` and return how many were deleted."""


def index_name(business_area: str, program_id: str) -> str:
    """Return the Elasticsearch index for one business area and program."""
    return f"biographic_{business_area}_{program_id}"


def document_id(dataset_id: int, reference_pk: str) -> str:
    """Return the Elasticsearch document id for one person in a dataset."""
    return f"{dataset_id}:{reference_pk}"
