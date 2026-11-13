"""Connection handling and the error paths that a live cluster will not produce."""

import pytest
from django.core.exceptions import ImproperlyConfigured
from elasticsearch import BadRequestError, NotFoundError

from hope_dedup_engine.apps.biographic.search import client, index
from hope_dedup_engine.apps.biographic.search.backend import ElasticsearchBiographicSearch


@pytest.fixture(autouse=True)
def _clear_client_cache():
    client._build_client.cache_clear()
    yield
    client._build_client.cache_clear()


def api_error(error_class, error_type, mocker):
    """Build the exception shape elasticsearch-py raises: message is the ES error type."""
    return error_class(error_type, meta=mocker.Mock(), body={"error": {"type": error_type}})


def test_a_missing_host_is_a_configuration_error(settings):
    settings.ELASTICSEARCH_HOST = ""

    with pytest.raises(ImproperlyConfigured, match="ELASTICSEARCH_HOST"):
        client.get_client()


def test_the_client_is_built_once_per_host(settings):
    settings.ELASTICSEARCH_HOST = "http://elasticsearch:9200"

    assert client.get_client() is client.get_client()


def test_find_indices_sorts_and_tolerates_a_missing_pattern(mocker):
    es_client = mocker.Mock()
    es_client.cat.indices.return_value = mocker.Mock(body=[{"index": "b_2"}, {"index": "a_1"}])

    assert client.find_indices(es_client, "pattern_*") == ["a_1", "b_2"]

    es_client.cat.indices.side_effect = api_error(NotFoundError, "index_not_found_exception", mocker)
    assert client.find_indices(es_client, "pattern_*") == []


def test_the_backend_builds_its_own_client_when_not_given_one(mocker, settings):
    settings.ELASTICSEARCH_HOST = "http://elasticsearch:9200"
    built = mocker.patch.object(client, "get_client")

    assert ElasticsearchBiographicSearch().client is built.return_value


def test_losing_the_create_race_still_leaves_the_index_in_place(mocker, es_settings):
    """Two workers can call ensure_index at once; the caller only asked for an index."""
    es_client = mocker.Mock()
    es_client.indices.exists.return_value = False
    es_client.cat.plugins.return_value = mocker.Mock(body=[{"component": index.PHONETIC_PLUGIN}])
    es_client.indices.create.side_effect = api_error(BadRequestError, "resource_already_exists_exception", mocker)

    name = ElasticsearchBiographicSearch(es_client=es_client).ensure_index("afghanistan", "1")

    assert name == index.index_name("afghanistan", "1")


def test_any_other_creation_failure_is_raised(mocker, es_settings):
    es_client = mocker.Mock()
    es_client.indices.exists.return_value = False
    es_client.cat.plugins.return_value = mocker.Mock(body=[{"component": index.PHONETIC_PLUGIN}])
    es_client.indices.create.side_effect = api_error(BadRequestError, "mapper_parsing_exception", mocker)

    with pytest.raises(BadRequestError):
        ElasticsearchBiographicSearch(es_client=es_client).ensure_index("afghanistan", "1")
