import os
from uuid import uuid4

import pytest
from elasticsearch import Elasticsearch

from hope_dedup_engine.apps.biographic.search import index
from hope_dedup_engine.apps.biographic.search.backend import ElasticsearchBiographicSearch

TEST_PREFIX = "test_"

DEFAULT_HOST = "http://localhost:9200"


@pytest.fixture(scope="session")
def es_client():
    host = os.environ.get("ELASTICSEARCH_HOST") or DEFAULT_HOST
    client = Elasticsearch(hosts=[host], request_timeout=10)
    try:
        reachable = client.ping()
    except Exception:  # noqa: BLE001 - any transport failure means "no cluster here"
        reachable = False
    if not reachable:
        pytest.skip(f"No Elasticsearch cluster at {host}")

    installed = {row.get("component") for row in client.cat.plugins(format="json")}
    if index.PHONETIC_PLUGIN not in installed:
        pytest.skip(f"Elasticsearch at {host} has no {index.PHONETIC_PLUGIN} plugin")
    return client


@pytest.fixture
def es_settings(settings):
    settings.ELASTICSEARCH_PREFIX = TEST_PREFIX
    settings.ELASTICSEARCH_SYNONYMS_FILE = ""
    return settings


@pytest.fixture
def search(es_client, es_settings):
    return ElasticsearchBiographicSearch(es_client=es_client)


@pytest.fixture
def make_group(es_client, search):
    """Create empty indexes for one business area and program, removed afterwards."""
    created = []

    def _make_group(program_code: str = "ab12") -> tuple[str, str]:
        business_area = f"ba{uuid4().hex[:8]}"
        search.ensure_index(business_area, program_code)
        created.append(index.index_name(business_area, program_code))
        return business_area, program_code

    yield _make_group

    for name in created:
        es_client.indices.delete(index=name, ignore_unavailable=True)


@pytest.fixture
def group(make_group):
    return make_group()
