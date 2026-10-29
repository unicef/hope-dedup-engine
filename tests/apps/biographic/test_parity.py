"""Scoring parity with HOPE.

HOPE's thresholds are calibrated against its own cluster, so the risk named in
issue #324 is that the same records land on a different side of the line here.
These tests reproduce the fixtures of HOPE's
`tests/unit/apps/registration_data/test_deduplication.py` and assert the same
classification it asserts: four duplicates and three uniques within the batch,
and five duplicates, one needs-adjudication and one unique against the
population. HOPE reaches that with two passes; we reach it with one search whose
hits are split by `status`, which is the point of the single-query design.

Field values are copied verbatim from HOPE's factories, including its
relationship and sex literals.
"""

import pytest

from testutils.biographic import make_payload

pytestmark = pytest.mark.elasticsearch

DUPLICATE_SCORE = 14.0
POSSIBLE_DUPLICATE_SCORE = 11.0

DUPLICATE = "duplicate"
NEEDS_ADJUDICATION = "needs_adjudication"
UNIQUE = "unique"

PENDING_DATASET = 1
POPULATION_DATASET = 2

# given_name, family_name, full_name, birth_date, phone_no, relationship, sex
PENDING_RECORDS = {
    "head": ("Test", "Testowski", "Test Testowski", "1955-09-04", "123-123-123", "HEAD", "MALE"),
    "tesa": ("Tesa", "Testowski", "Tesa Testowski", "1957-10-10", "123-123-123", "WIFE_HUSBAND", "FEMALE"),
    "tescik": ("Tescik", "Testowski", "Tescik Testowski", "1996-12-12", "123-123-123", "SON_DAUGHTER", "MALE"),
    "tessta": ("Tessta", "Testowski", "Tessta Testowski", "1997-07-07", "123-123-123", "SON_DAUGHTER", "FEMALE"),
    "head_again": ("Test", "Testowski", "Test Testowski", "1955-09-04", "123-123-123", "HEAD", "MALE"),
    "example": ("Test", "Example", "Test Example", "1997-08-08", "432-125-765", "SON_DAUGHTER", "MALE"),
    "tessta_again": ("Tessta", "Testowski", "Tessta Testowski", "1997-07-07", "123-123-123", "SON_DAUGHTER", "FEMALE"),
}

POPULATION_RECORDS = {
    "merged_head": ("Test", "Testowski", "Test Testowski", "1955-09-04", "123-123-123", "HEAD", "MALE"),
    "merged_example": ("Test", "Example", "Test Example", "1997-08-08", "432-125-765", "SON_DAUGHTER", "MALE"),
    "merged_tessta": ("Tessta", "Testowski", "Tessta Testowski", "1997-07-07", "123-123-123", "SON_DAUGHTER", "FEMALE"),
    "merged_tescik": ("Tescik", "Testowski", "Tescik Testowski", "1996-12-12", "666-777-888", "SON_DAUGHTER", "MALE"),
}

# HOPE: duplicate_in_batch == 4, unique_in_batch == 3
EXPECTED_IN_BATCH = {
    "head": DUPLICATE,
    "tesa": UNIQUE,
    "tescik": UNIQUE,
    "tessta": DUPLICATE,
    "head_again": DUPLICATE,
    "example": UNIQUE,
    "tessta_again": DUPLICATE,
}

# HOPE: duplicate == 5, needs_adjudication == 1, unique == 1
EXPECTED_AGAINST_POPULATION = {
    "head": DUPLICATE,
    "tesa": UNIQUE,
    "tescik": NEEDS_ADJUDICATION,
    "tessta": DUPLICATE,
    "head_again": DUPLICATE,
    "example": DUPLICATE,
    "tessta_again": DUPLICATE,
}


def to_payload(reference_pk, record):
    given_name, family_name, full_name, birth_date, phone_no, relationship, sex = record
    return make_payload(
        reference_pk,
        given_name=given_name,
        family_name=family_name,
        full_name=full_name,
        middle_name="",
        birth_date=birth_date,
        phone_no=phone_no,
        phone_no_alternative="",
        relationship=relationship,
        sex=sex,
    )


def classify(score):
    if score >= DUPLICATE_SCORE:
        return DUPLICATE
    if score >= POSSIBLE_DUPLICATE_SCORE:
        return NEEDS_ADJUDICATION
    return UNIQUE


def best_scores(search, group):
    """Score every record with one search each, then split the hits by side.

    The split is what the service will do: HOPE's two passes become one query
    plus a filter on `status`.
    """
    business_area, program_code = group
    in_batch, against_population = {}, {}
    for reference_pk, record in PENDING_RECORDS.items():
        hits = search.search(
            business_area,
            program_code,
            to_payload(reference_pk, record),
            min_score=POSSIBLE_DUPLICATE_SCORE,
            dataset_id=PENDING_DATASET,
        )
        in_batch[reference_pk] = best(hits, "pending")
        against_population[reference_pk] = best(hits, "approved")
    return in_batch, against_population


def best(hits, status):
    return max((hit.score for hit in hits if hit.status == status), default=0.0)


@pytest.fixture
def hope_fixture(search, group):
    business_area, program_code = group
    search.index_records(
        business_area,
        program_code,
        PENDING_DATASET,
        [to_payload(pk, record) for pk, record in PENDING_RECORDS.items()],
    )
    search.index_records(
        business_area,
        program_code,
        POPULATION_DATASET,
        [to_payload(pk, record) for pk, record in POPULATION_RECORDS.items()],
    )
    # update_by_query only sees refreshed documents, so the population has to be
    # searchable before it can be approved.
    search.refresh(business_area, program_code)
    search.set_status(business_area, program_code, POPULATION_DATASET, "approved")
    return group


def test_batch_parity_with_hope(search, hope_fixture):
    in_batch, _ = best_scores(search, hope_fixture)

    classification = {pk: classify(score) for pk, score in in_batch.items()}

    assert classification == EXPECTED_IN_BATCH, in_batch


def test_population_parity_with_hope(search, hope_fixture):
    _, against_population = best_scores(search, hope_fixture)

    classification = {pk: classify(score) for pk, score in against_population.items()}

    assert classification == EXPECTED_AGAINST_POPULATION, against_population


def test_identical_records_score_at_the_duplicate_threshold(search, hope_fixture):
    """Both names 8, birth date 2, phone 2, sex 1, relationship 1."""
    in_batch, _ = best_scores(search, hope_fixture)

    assert in_batch["head"] == pytest.approx(DUPLICATE_SCORE, abs=0.5), in_batch
