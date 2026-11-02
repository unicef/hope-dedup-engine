"""Data crossing the boundary between the biographic service and the search library.

Plain frozen dataclasses, deliberately not serializers: validation happens once,
at the API edge, and everything here is already-validated data on its way to or
from Elasticsearch. Keeping them free of DRF also keeps the search library
importable without the request cycle.

Shared with the service issues, so a change here needs their assignees to agree.
"""

from dataclasses import dataclass

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
    similarity score. Identity documents are deliberately absent: matching them is
    exact rather than fuzzy, so it belongs in Postgres, which is where HOPE does it
    too (`HardDocumentDeduplication`, a separate task from the Elasticsearch pass).
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
