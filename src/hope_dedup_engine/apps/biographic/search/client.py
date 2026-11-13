"""Connection handling for the biographic Elasticsearch cluster.

A dedicated cluster, separate from HOPE's historical one. This module knows how to
reach it, how to check it can do the job, and how to list the indexes we own. It
holds no Django state beyond settings, so it is importable from a worker without
the ORM.
"""

from functools import lru_cache
from typing import cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from elasticsearch import Elasticsearch, NotFoundError

from hope_dedup_engine.apps.biographic.search import index

REQUEST_TIMEOUT = 30

# HOPE's chunk size for bulk indexing.
BULK_CHUNK_SIZE = 2000


class PhoneticPluginMissingError(RuntimeError):
    """The cluster cannot build the analyzers that HOPE's scoring depends on."""


@lru_cache(maxsize=4)
def _build_client(host: str) -> Elasticsearch:
    return Elasticsearch(hosts=[host], request_timeout=REQUEST_TIMEOUT)


def get_client() -> Elasticsearch:
    host = settings.ELASTICSEARCH_HOST
    if not host:
        raise ImproperlyConfigured("ELASTICSEARCH_HOST is not set, biographic deduplication cannot reach a cluster.")
    return _build_client(host)


def verify_phonetic_plugin(client: Elasticsearch) -> None:
    """Fail early and legibly when the cluster lacks `analysis-phonetic`.

    Without the plugin, index creation fails with a mapping error that says
    nothing about the real cause.
    """
    rows = cast("list[dict[str, str]]", client.cat.plugins(format="json").body)
    installed = {row.get("component") for row in rows}
    if index.PHONETIC_PLUGIN not in installed:
        raise PhoneticPluginMissingError(
            f"The Elasticsearch cluster has no {index.PHONETIC_PLUGIN!r} plugin, "
            f"so the phonetic analyzer cannot be created. Installed plugins: {sorted(filter(None, installed))}."
        )


def find_indices(client: Elasticsearch, pattern: str) -> list[str]:
    """List the existing indexes matching a pattern, by name."""
    try:
        response = client.cat.indices(index=pattern, format="json", h="index")
    except NotFoundError:
        return []
    rows = cast("list[dict[str, str]]", response.body)
    return sorted(row["index"] for row in rows)
