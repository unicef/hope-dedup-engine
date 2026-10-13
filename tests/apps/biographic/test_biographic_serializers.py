import pytest

from hope_dedup_engine.apps.biographic.schemas import PAYLOAD_FIELDS
from hope_dedup_engine.apps.biographic.serializers import (
    BiographicPayloadSerializer,
    ProcessOverridesSerializer,
)

FULL_PAYLOAD = {
    "given_name": "Maria",
    "middle_name": "",
    "family_name": "Gonzalez",
    "full_name": "Maria Gonzalez",
    "birth_date": "1990-05-15",
    "phone_no": "+93 700 000 001",
    "phone_no_alternative": None,
    "sex": "FEMALE",
    "relationship": "HEAD",
}


def validated(data):
    serializer = BiographicPayloadSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    return serializer.validated_data


def errors(data):
    serializer = BiographicPayloadSerializer(data=data)
    assert not serializer.is_valid()
    return serializer.errors


def test_fields_are_generated_from_the_contract():
    assert tuple(BiographicPayloadSerializer().fields) == PAYLOAD_FIELDS


def test_a_full_payload_round_trips_unchanged():
    assert validated(FULL_PAYLOAD) == FULL_PAYLOAD


def test_every_field_is_optional_and_absent_keys_stay_absent():
    assert validated({"full_name": "Maria"}) == {"full_name": "Maria"}
    assert validated({}) == {}


def test_unknown_keys_are_dropped_not_rejected():
    data = {"full_name": "Maria", "identities": [{"number": "1", "partner": "UNHCR"}], "admin1": "AF01"}
    assert validated(data) == {"full_name": "Maria"}


def test_whitespace_is_kept_as_sent():
    assert validated({"given_name": "  Maria "}) == {"given_name": "  Maria "}


@pytest.mark.parametrize("value", ["15/05/1990", "1990-13-01", "1990-05-15T10:00:00", "yesterday", 19900515])
def test_birth_date_must_be_an_iso_date(value):
    assert "birth_date" in errors({"birth_date": value})


def test_birth_date_is_stored_as_a_canonical_iso_string():
    assert validated({"birth_date": "1990-5-15"}) == {"birth_date": "1990-05-15"}


def test_text_fields_reject_structures():
    assert "full_name" in errors({"full_name": {"first": "Maria"}})


def test_process_overrides_accept_known_settings():
    serializer = ProcessOverridesSerializer(data={"duplicate_score": 11, "max_hits": 20})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {"duplicate_score": 11.0, "max_hits": 20}


def test_process_overrides_may_be_empty():
    serializer = ProcessOverridesSerializer(data={})
    assert serializer.is_valid()
    assert serializer.validated_data == {}


def test_a_misspelt_setting_is_an_error_not_ignored():
    serializer = ProcessOverridesSerializer(data={"duplicate_scor": 11})
    assert not serializer.is_valid()
    assert serializer.errors == {"duplicate_scor": ["Unknown setting."]}


@pytest.mark.parametrize(("name", "value"), [("duplicate_score", -1), ("max_hits", 0), ("max_hits", 1.5)])
def test_process_overrides_are_range_and_type_checked(name, value):
    serializer = ProcessOverridesSerializer(data={name: value})
    assert not serializer.is_valid()
    assert name in serializer.errors
