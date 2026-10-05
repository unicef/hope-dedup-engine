"""Integration tests against a real cluster.

The query path is never mocked: the point of these tests is that the engine
itself produces the expected scores.
"""

import pytest

from hope_dedup_engine.apps.biographic.search import index

from testutils.biographic import make_payload

pytestmark = pytest.mark.elasticsearch

DATASET = 1


def index_records(search, group, records, dataset_id=DATASET):
    business_area, program_code = group
    indexed = search.index_records(business_area, program_code, dataset_id, records)
    search.refresh(business_area, program_code)
    return indexed


def find(search, group, payload, *, min_score=0.0, dataset_id=DATASET, size=100):
    business_area, program_code = group
    return search.search(
        business_area,
        program_code,
        payload,
        min_score=min_score,
        dataset_id=dataset_id,
        size=size,
    )


def best_score(hits):
    return hits[0].score if hits else 0.0


def test_index_records_counts_and_needs_a_refresh(search, group):
    business_area, program_code = group
    records = [
        make_payload("a", given_name="Test", family_name="Testowski", full_name="Test Testowski"),
        make_payload("b", given_name="Tesa", family_name="Testowski", full_name="Tesa Testowski"),
    ]

    indexed = search.index_records(business_area, program_code, DATASET, records)
    assert indexed == 2

    probe = make_payload("probe", given_name="Test", family_name="Testowski", full_name="Test Testowski")
    assert find(search, group, probe) == []

    search.refresh(business_area, program_code)
    assert len(find(search, group, probe)) == 2


def test_indexing_nothing_is_not_an_error(search, group):
    business_area, program_code = group

    assert search.index_records(business_area, program_code, DATASET, []) == 0


def test_phonetic_match_on_spelling_variants(search, group):
    index_records(
        search,
        group,
        [make_payload("a", given_name="Stephen", family_name="Smith", full_name="Stephen Smith")],
    )

    hits = find(search, group, make_payload("b", given_name="Steven", family_name="Smith", full_name="Steven Smith"))

    assert [hit.reference_pk for hit in hits] == ["a"]


def test_fuzzy_matches_a_typo_but_not_a_different_name(search, group):
    index_records(
        search,
        group,
        [make_payload("a", given_name="Barbara", family_name="Kowalski", full_name="Barbara Kowalski")],
    )

    typo = find(search, group, make_payload("b", given_name="Barbora", family_name="Kowalski"))
    different = find(search, group, make_payload("c", given_name="Zygmunt", family_name="Kowalski"))

    # Both names match through the `must` branch, so the typo scores about 8.
    assert best_score(typo) > 4
    # Only the family name matches, so this resolves through `should`, about 1.
    assert best_score(different) < 2


def test_both_names_score_materially_higher_than_one(search, group):
    index_records(
        search,
        group,
        [
            make_payload("both", given_name="Test", family_name="Testowski", full_name="Test Testowski"),
            make_payload("family", given_name="Zygmunt", family_name="Testowski", full_name="Zygmunt Testowski"),
        ],
    )

    hits = {
        hit.reference_pk: hit.score
        for hit in find(search, group, make_payload("q", given_name="Test", family_name="Testowski"))
    }

    assert hits["both"] > 3 * hits["family"]


def test_full_name_fallback_fires_when_a_name_is_missing(search, group):
    index_records(
        search,
        group,
        [make_payload("a", given_name="Test", family_name="Testowski", full_name="Test Testowski")],
    )

    hits = find(search, group, make_payload("b", full_name="Test Testowski"))

    assert [hit.reference_pk for hit in hits] == ["a"]
    assert best_score(hits) == pytest.approx(8.0, abs=0.5)


def test_min_score_drops_weak_matches(search, group):
    index_records(
        search,
        group,
        [make_payload("a", given_name="Zygmunt", family_name="Testowski", full_name="Zygmunt Testowski")],
    )
    probe = make_payload("b", given_name="Test", family_name="Testowski")

    assert find(search, group, probe, min_score=0.5) != []
    assert find(search, group, probe, min_score=5.0) == []


def test_the_record_itself_is_excluded(search, group):
    records = [
        make_payload("a", given_name="Test", family_name="Testowski", full_name="Test Testowski"),
        make_payload("b", given_name="Test", family_name="Testowski", full_name="Test Testowski"),
    ]
    index_records(search, group, records)

    hits = find(search, group, records[0])

    assert [hit.reference_pk for hit in hits] == ["b"]


def test_an_approved_copy_of_the_same_reference_pk_is_excluded_too(search, group):
    """A reference_pk names one person, so a record never matches an earlier copy of itself."""
    business_area, program_code = group
    record = make_payload("same-pk", given_name="Test", family_name="Testowski", full_name="Test Testowski")
    index_records(search, group, [record], dataset_id=99)
    search.set_status(business_area, program_code, 99, "approved")
    index_records(search, group, [record], dataset_id=DATASET)

    assert find(search, group, record) == []


def test_one_search_returns_both_sides_and_says_which_is_which(search, group):
    business_area, program_code = group
    index_records(search, group, [make_payload("approved", given_name="Test", family_name="Testowski")], dataset_id=2)
    search.set_status(business_area, program_code, 2, "approved")
    index_records(search, group, [make_payload("pending", given_name="Test", family_name="Testowski")])

    hits = find(search, group, make_payload("q", given_name="Test", family_name="Testowski"))

    assert {hit.reference_pk: (hit.dataset_id, hit.status) for hit in hits} == {
        "pending": (DATASET, "pending"),
        "approved": (2, "approved"),
    }


def test_other_datasets_still_pending_are_not_candidates(search, group):
    """Two batches in flight must not see each other: only approved records are shared."""
    index_records(search, group, [make_payload("other", given_name="Test", family_name="Testowski")], dataset_id=2)
    index_records(search, group, [make_payload("mine", given_name="Test", family_name="Testowski")])

    hits = find(search, group, make_payload("q", given_name="Test", family_name="Testowski"))

    assert [hit.reference_pk for hit in hits] == ["mine"]


def test_rejected_records_are_not_candidates(search, group):
    business_area, program_code = group
    index_records(search, group, [make_payload("rejected", given_name="Test", family_name="Testowski")], dataset_id=2)
    search.set_status(business_area, program_code, 2, "rejected")

    assert find(search, group, make_payload("q", given_name="Test", family_name="Testowski")) == []


def test_other_groups_are_never_searched(search, make_group):
    mine = make_group()
    theirs = make_group()
    index_records(search, theirs, [make_payload("theirs", given_name="Test", family_name="Testowski")])
    index_records(search, mine, [make_payload("mine", given_name="Test", family_name="Testowski")])

    hits = find(search, mine, make_payload("q", given_name="Test", family_name="Testowski"))

    assert [hit.reference_pk for hit in hits] == ["mine"]


def test_set_status_touches_only_the_target_dataset(search, group, es_client):
    business_area, program_code = group
    index_records(search, group, [make_payload("a", given_name="Test", family_name="Testowski")], dataset_id=1)
    index_records(search, group, [make_payload("b", given_name="Test", family_name="Testowski")], dataset_id=2)

    updated = search.set_status(business_area, program_code, 1, "approved")

    assert updated == 1
    name = index.index_name(business_area, program_code)
    assert es_client.get(index=name, id="1:a")["_source"]["status"] == "approved"
    assert es_client.get(index=name, id="2:b")["_source"]["status"] == "pending"


def test_rejected_cleanup_reports_per_index_and_spares_the_rest(search, make_group, es_client):
    first = make_group()
    second = make_group()
    for group in (first, second):
        business_area, program_code = group
        index_records(
            search, group, [make_payload("rejected", given_name="Test", family_name="Testowski")], dataset_id=1
        )
        search.set_status(business_area, program_code, 1, "rejected")
        index_records(
            search, group, [make_payload("approved", given_name="Test", family_name="Testowski")], dataset_id=2
        )
        search.set_status(business_area, program_code, 2, "approved")
        index_records(
            search, group, [make_payload("pending", given_name="Test", family_name="Testowski")], dataset_id=3
        )

    deleted = search.delete_by_status("rejected")

    for group in (first, second):
        name = index.index_name(*group)
        assert deleted[name] == 1
        remaining = {
            hit["_source"]["reference_pk"]: hit["_source"]["status"]
            for hit in es_client.search(index=name, query={"match_all": {}})["hits"]["hits"]
        }
        assert remaining == {"approved": "approved", "pending": "pending"}
