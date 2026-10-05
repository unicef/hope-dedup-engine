"""Query builder, ported from HOPE's `DeduplicateTask`.

One function per HOPE method, in HOPE's order, so a reviewer can diff this file
against `hope/apps/registration_data/tasks/deduplicate.py` side by side:

* `build_query` <- `_prepare_query_dict`
* `queries_for_names` <- `_prepare_queries_for_names_from_fields`
* `complex_query_for_name` <- `_get_complex_query_for_name`

Scoring behaviour is deliberately unchanged. HOPE's
`_prepare_identities_queries_from_fields` has no counterpart here: identity
documents are matched exactly, which is a Postgres job, and HOPE itself does it
there in `HardDocumentDeduplication` rather than through Elasticsearch.
"""

from typing import Any

from hope_dedup_engine.apps.biographic import contracts

FUZZINESS = "AUTO:3,6"

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"

# HOPE's `fields_meta`, minus `admin1` and `admin2`: nothing ever populates those
# into the query input, so they never contribute a clause.
SCALAR_BOOSTS = {
    "birth_date": 2,
    "phone_no": 2,
    "phone_no_alternative": 2,
    "sex": 1,
    "relationship": 1,
    "middle_name": 1,
}


def build_query(
    payload: contracts.BiographicPayload,
    *,
    min_score: float,
    dataset_id: int,
    size: int = 100,
) -> dict[str, Any]:
    """Build the full search body for one record.

    `should` clauses add to the score, `filter` restricts without scoring, and
    `min_score` drops everything below the caller's bar. Pass the lowest
    threshold that interests you: classifying a score is the service's job.
    """
    queries: list[dict[str, Any]] = []
    queries.extend(queries_for_names(payload))
    queries.extend(scalar_queries(payload))

    return {
        "min_score": min_score,
        "size": size,
        "query": {
            "bool": {
                "minimum_should_match": 1,
                "should": queries,
                "must_not": [self_exclusion(payload.reference_pk)],
                "filter": candidate_filter(dataset_id),
            },
        },
    }


def queries_for_names(payload: contracts.BiographicPayload) -> list[dict[str, Any]]:
    """Build the name clause.

    Three branches:

    1. no name at all, so no clause
    2. given or family missing, so one `full_name` match at boost 8
    3. both present, so the best of "either name matched" and "both names matched"
    """
    given_name = payload.given_name
    family_name = payload.family_name
    full_name = payload.full_name

    if not any((given_name, family_name, full_name)):
        return []

    if not given_name or not family_name:
        # max possible score 8
        return [
            {
                "match": {
                    "full_name": {
                        "query": full_name,
                        "boost": 8.0,
                        "operator": "AND",
                    },
                },
            }
        ]

    given_name_complex_query = complex_query_for_name(given_name, "given_name")
    family_name_complex_query = complex_query_for_name(family_name, "family_name")
    names_should_query = {
        "bool": {
            "should": [
                given_name_complex_query,
                family_name_complex_query,
            ],
        },
    }
    # max possible score 8
    names_must_query = {
        "bool": {
            "must": [
                given_name_complex_query,
                family_name_complex_query,
            ],
            "boost": 4,
        },
    }
    # `tie_breaker: 0` takes the best branch, not the sum: both names matching
    # resolves through `must` at about 4 * (1 + 1), one name gives about 1.
    return [
        {
            "dis_max": {
                "queries": [names_should_query, names_must_query],
                "tie_breaker": 0,
            },
        }
    ]


def complex_query_for_name(name: str, field_name: str) -> dict[str, Any]:
    """Match one name by spelling or by sound, whichever scores better."""
    name_phonetic_query_dict = {"match": {f"{field_name}.phonetic": {"query": name}}}
    # phonetic analyzer not working with fuzziness
    name_fuzzy_query_dict = {
        "match": {
            field_name: {
                "query": name,
                "fuzziness": FUZZINESS,
                "max_expansions": 50,
                "prefix_length": 0,
                "fuzzy_transpositions": True,
            },
        },
    }
    # choose max from fuzzy and phonetic
    # phonetic score === 0 or 1
    # fuzzy score <=1 changes if there is need make change
    return {
        "dis_max": {
            "queries": [name_fuzzy_query_dict, name_phonetic_query_dict],
            "tie_breaker": 0,
        },
    }


def scalar_queries(payload: contracts.BiographicPayload) -> list[dict[str, Any]]:
    """Match the single-value fields, each at HOPE's boost. Null and empty are skipped."""
    queries: list[dict[str, Any]] = []
    for field_name, boost in SCALAR_BOOSTS.items():
        field_value = getattr(payload, field_name)
        if field_value is None:
            continue
        if isinstance(field_value, str) and field_value == "":
            continue
        queries.append(
            {
                "match": {
                    field_name: {
                        "query": field_value,
                        "boost": boost,
                        "operator": "OR",
                    },
                },
            }
        )
    return queries


def candidate_filter(dataset_id: int) -> dict[str, Any]:
    """Restrict the search to everything worth comparing against, without scoring.

    That is the rest of this dataset, still pending, plus the whole approved
    population. One search covers both: a hit carries its own `dataset_id` and
    `status`, so the service can tell the two apart afterwards without paying for
    a second query. The index is already one business area and program, so
    nothing here needs to say so again.

    Rejected records are never candidates, and neither are other datasets that
    are still pending: two batches in flight at once must not see each other.
    """
    return {
        "bool": {
            "minimum_should_match": 1,
            "should": [
                {
                    "bool": {
                        "must": [
                            {"term": {"dataset_id": dataset_id}},
                            {"term": {"status": STATUS_PENDING}},
                        ],
                    },
                },
                {"term": {"status": STATUS_APPROVED}},
            ],
        },
    }


def self_exclusion(reference_pk: str) -> dict[str, Any]:
    """Exclude every document carrying this `reference_pk`.

    A caller must not reuse a `reference_pk` for two different people, so this
    never hides a genuine duplicate.
    """
    return {"term": {"reference_pk": reference_pk}}
