"""Unit tests for the query builder. No cluster involved: these assert structure."""

from hope_dedup_engine.apps.biographic.search import query

from testutils.biographic import make_payload


def build(payload, **kwargs):
    defaults = {
        "min_score": 11.0,
        "dataset_id": 7,
    }
    return query.build_query(payload, **{**defaults, **kwargs})


def test_no_names_emits_no_name_clause():
    payload = make_payload("1", sex="MALE")

    assert query.queries_for_names(payload) == []


def test_missing_given_name_falls_back_to_full_name():
    payload = make_payload("1", family_name="Testowski", full_name="Test Testowski")

    clauses = query.queries_for_names(payload)

    assert clauses == [
        {"match": {"full_name": {"query": "Test Testowski", "boost": 8.0, "operator": "AND"}}},
    ]


def test_both_names_combine_should_and_must():
    payload = make_payload("1", given_name="Test", family_name="Testowski", full_name="Test Testowski")

    [clause] = query.queries_for_names(payload)

    should_branch, must_branch = clause["dis_max"]["queries"]
    assert clause["dis_max"]["tie_breaker"] == 0
    assert len(should_branch["bool"]["should"]) == 2
    assert must_branch["bool"]["boost"] == 4


def test_each_name_takes_the_best_of_fuzzy_and_phonetic():
    clause = query.complex_query_for_name("Test", "given_name")

    fuzzy, phonetic = clause["dis_max"]["queries"]
    assert clause["dis_max"]["tie_breaker"] == 0
    assert fuzzy["match"]["given_name"]["fuzziness"] == "AUTO:3,6"
    assert fuzzy["match"]["given_name"]["max_expansions"] == 50
    assert fuzzy["match"]["given_name"]["prefix_length"] == 0
    assert fuzzy["match"]["given_name"]["fuzzy_transpositions"] is True
    assert phonetic == {"match": {"given_name.phonetic": {"query": "Test"}}}


def test_scalar_clauses_carry_hope_boosts():
    payload = make_payload(
        "1",
        birth_date="1955-09-04",
        phone_no="123-123-123",
        sex="MALE",
        relationship="HEAD",
    )

    boosts = {field: clause["match"][field]["boost"] for clause, field in _clause_fields(query.scalar_queries(payload))}

    assert boosts == {"birth_date": 2, "phone_no": 2, "sex": 1, "relationship": 1}


def test_scalar_clauses_skip_null_and_empty():
    payload = make_payload("1", sex="MALE", relationship="", middle_name=None)

    fields = [field for _, field in _clause_fields(query.scalar_queries(payload))]

    assert fields == ["sex"]


def test_one_filter_covers_this_dataset_and_the_approved_population():
    body = build(make_payload("1", sex="MALE"))

    clauses = body["query"]["bool"]["filter"]["bool"]
    assert clauses["minimum_should_match"] == 1
    assert clauses["should"] == [
        {
            "bool": {
                "must": [
                    {"term": {"dataset_id": 7}},
                    {"term": {"status": "pending"}},
                ],
            },
        },
        {"term": {"status": "approved"}},
    ]


def test_self_exclusion_keys_on_the_reference_pk():
    """A reference_pk identifies one person, so excluding it never hides a real duplicate."""
    body = build(make_payload("abc", sex="MALE"), dataset_id=7)

    assert body["query"]["bool"]["must_not"] == [{"term": {"reference_pk": "abc"}}]


def test_min_score_and_size_reach_the_body():
    body = build(make_payload("1", sex="MALE"), min_score=14.0, size=25)

    assert body["min_score"] == 14.0
    assert body["size"] == 25
    assert body["query"]["bool"]["minimum_should_match"] == 1


def _clause_fields(clauses):
    return [(clause, next(iter(clause["match"]))) for clause in clauses]
