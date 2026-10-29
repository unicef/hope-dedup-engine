from collections import defaultdict
from dataclasses import dataclass, field

from elasticsearch import NotFoundError

from hope_dedup_engine.apps.biographic.schemas import PAYLOAD_FIELDS, BiographicPayload, Hit


def make_payload(reference_pk: str, **fields) -> BiographicPayload:
    """Build a payload, defaulting every scoreable field the caller does not set."""
    values: dict = dict.fromkeys(PAYLOAD_FIELDS)
    values.update(fields)
    return BiographicPayload(reference_pk=reference_pk, **values)


@dataclass
class FakeDocument:
    payload: BiographicPayload
    dataset_id: int
    status: str = "pending"


@dataclass
class FakeBiographicSearch:
    """In-memory `BiographicSearch` with HOPE's candidate rules and a trivial score.

    Two documents match when their `full_name` is equal, case-insensitively;
    the score is `match_score`. Exactly the filter `query.candidate_filter`
    applies: the caller's own pending dataset plus the approved population,
    never the record itself. Enough to test everything around the search
    without a cluster; the scoring itself is covered against a real one.
    """

    match_score: float = 10.0
    indexes: dict[str, dict[str, FakeDocument]] = field(default_factory=lambda: defaultdict(dict))
    calls: list[tuple] = field(default_factory=list)
    fail_on: str | None = None

    @staticmethod
    def index_name(business_area: str, program_code: str) -> str:
        return f"{business_area}_{program_code}"

    def _check(self, method: str) -> None:
        if self.fail_on == method:
            raise RuntimeError(f"{method} failed")

    def index_exists(self, business_area: str, program_code: str) -> bool:
        return self.index_name(business_area, program_code) in self.indexes

    def ensure_index(self, business_area: str, program_code: str) -> str:
        self._check("ensure_index")
        self.calls.append(("ensure_index", business_area, program_code))
        name = self.index_name(business_area, program_code)
        self.indexes[name]  # noqa: B018 - creates the index
        return name

    def index_records(self, business_area, program_code, dataset_id, records, status="pending"):
        self._check("index_records")
        self.calls.append(("index_records", dataset_id, len(records)))
        docs = self.indexes[self.index_name(business_area, program_code)]
        for record in records:
            docs[f"{dataset_id}:{record.reference_pk}"] = FakeDocument(record, dataset_id, status)
        return len(records)

    def refresh(self, business_area, program_code):
        self.calls.append(("refresh",))

    def search(self, business_area, program_code, payload, min_score, dataset_id, size=100):  # noqa: PLR0913, PLR0917
        docs = self.indexes[self.index_name(business_area, program_code)]
        hits = []
        for doc in docs.values():
            if doc.payload.reference_pk == payload.reference_pk:
                continue
            own_pending = doc.dataset_id == dataset_id and doc.status == "pending"
            if not (own_pending or doc.status == "approved"):
                continue
            if (doc.payload.full_name or "").lower() != (payload.full_name or "").lower():
                continue
            if self.match_score < min_score:
                continue
            hits.append(
                Hit(
                    reference_pk=doc.payload.reference_pk,
                    score=self.match_score,
                    dataset_id=doc.dataset_id,
                    status=doc.status,
                    full_name=doc.payload.full_name,
                    birth_date=doc.payload.birth_date,
                )
            )
        return hits[:size]

    def search_many(self, business_area, program_code, payloads, min_score, dataset_id, size=100):  # noqa: PLR0913, PLR0917
        self._check("search_many")
        self.calls.append(("search_many", dataset_id, len(payloads)))
        return [self.search(business_area, program_code, p, min_score, dataset_id, size) for p in payloads]

    def set_status(self, business_area, program_code, dataset_id, status):
        self._check("set_status")
        self.calls.append(("set_status", dataset_id, status))
        name = self.index_name(business_area, program_code)
        if name not in self.indexes:
            raise NotFoundError("index_not_found_exception", None, None)  # type: ignore[arg-type]
        updated = 0
        for doc in self.indexes[name].values():
            if doc.dataset_id == dataset_id:
                doc.status = status
                updated += 1
        return updated

    def delete_by_status(self, status):
        self.calls.append(("delete_by_status", status))
        deleted = {}
        for name, docs in self.indexes.items():
            doomed = [key for key, doc in docs.items() if doc.status == status]
            for key in doomed:
                del docs[key]
            deleted[name] = len(doomed)
        return deleted

    def documents(self, business_area: str, program_code: str) -> dict[str, FakeDocument]:
        return self.indexes[self.index_name(business_area, program_code)]
