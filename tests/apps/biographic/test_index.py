import pytest

from hope_dedup_engine.apps.biographic import schemas
from hope_dedup_engine.apps.biographic.search import client, index

from testutils.biographic import make_payload


def test_scoreable_mapping_matches_the_contract():
    """The serializer validates against PAYLOAD_FIELDS; the mapping may not drift from it."""
    assert index.scoreable_fields() == set(schemas.PAYLOAD_FIELDS)


def test_index_name_carries_business_area_and_program(es_settings):
    assert index.index_name("afghanistan", "ab12") == "test_biographic_afghanistan_ab12"


def test_index_pattern_covers_every_group(es_settings):
    assert index.index_pattern() == "test_biographic_*"


def test_similarity_script_is_hopes(es_settings):
    similarity = index.index_settings()["similarity"]["default"]

    assert similarity["type"] == "scripted"
    assert similarity["script"]["source"] == "return (1.0/doc.length)*query.boost"


def test_bundled_synonyms_are_used_when_unset(es_settings):
    synonyms = index.load_synonyms()

    assert any(line.startswith("johnathan,") for line in synonyms)


def test_synonyms_file_is_configurable(es_settings, tmp_path):
    path = tmp_path / "synonyms.txt"
    path.write_text("bill,william\n\n")
    es_settings.ELASTICSEARCH_SYNONYMS_FILE = str(path)

    assert index.load_synonyms() == ["bill,william"]


def test_document_carries_metadata_and_payload(es_settings):
    payload = make_payload("abc", given_name="Test", full_name="Test Testowski")

    document = index.to_document(payload, "afghanistan", "ab12", dataset_id=7)

    assert document["reference_pk"] == "abc"
    assert document["dataset_id"] == 7
    assert document["business_area"] == "afghanistan"
    assert document["program_code"] == "ab12"
    assert document["status"] == "pending"
    assert document["given_name"] == "Test"
    assert set(document) == set(schemas.PAYLOAD_FIELDS) | index.METADATA_FIELDS


def test_document_id_pairs_dataset_and_reference():
    assert index.document_id(7, "abc") == "7:abc"


@pytest.mark.elasticsearch
def test_ensure_index_is_idempotent(search, es_client, group):
    business_area, program_code = group
    name = index.index_name(business_area, program_code)
    before = es_client.indices.get(index=name)[name]

    assert search.ensure_index(business_area, program_code) == name
    assert es_client.indices.get(index=name)[name] == before


@pytest.mark.elasticsearch
def test_settings_and_mapping_round_trip(es_client, group):
    business_area, program_code = group
    name = index.index_name(business_area, program_code)

    created = es_client.indices.get(index=name)[name]

    settings_ = created["settings"]["index"]
    assert settings_["number_of_shards"] == "1"
    assert settings_["number_of_replicas"] == "0"
    assert settings_["similarity"]["default"]["script"]["source"] == index.SIMILARITY_SCRIPT
    assert settings_["analysis"]["analyzer"]["phonetic"] == {
        "tokenizer": "standard",
        "filter": ["lowercase", "my_metaphone"],
    }
    assert settings_["analysis"]["filter"]["my_metaphone"]["encoder"] == "double_metaphone"

    properties = created["mappings"]["properties"]
    assert properties["given_name"]["analyzer"] == "text_analyzer"
    assert properties["given_name"]["fields"]["phonetic"]["analyzer"] == "phonetic"
    assert properties["family_name"]["fields"]["phonetic"]["analyzer"] == "phonetic"
    assert properties["full_name"]["analyzer"] == "phonetic"
    assert properties["phone_no"]["similarity"] == "boolean"


def test_missing_phonetic_plugin_is_reported_clearly(mocker):
    es_client = mocker.Mock()
    es_client.cat.plugins.return_value = mocker.Mock(body=[{"component": "analysis-icu"}])

    with pytest.raises(client.PhoneticPluginMissingError, match="analysis-phonetic"):
        client.verify_phonetic_plugin(es_client)
