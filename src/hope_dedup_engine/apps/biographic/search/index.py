"""Index naming, settings and mapping for biographic deduplication.

Ported from HOPE, which is the calibration reference for every score this library
produces:

* ``hope/apps/household/documents.py`` - index settings and ``IndividualDocument``
* ``hope/apps/core/es_analyzers.py`` - phonetic and synonym analyzers
* ``hope/apps/utils/elasticsearch_utils.py`` - the similarity script

Fidelity matters more than elegance here. The duplicate thresholds downstream are
calibrated against these exact settings, so a change to the similarity script, an
analyzer or a field type silently invalidates them.
"""

from pathlib import Path
from typing import Any

from django.conf import settings

from hope_dedup_engine.apps.biographic import schemas

# HOPE replaces Elasticsearch's default BM25 relevance with this script, as an
# index-level default. A matching text field then scores roughly
# `boost / token_count`, and term rarity stops mattering: "Smith" and
# "Abdulrahman" are worth the same. Without it every score, and therefore every
# threshold downstream, is wrong.
SIMILARITY_SCRIPT = "return (1.0/doc.length)*query.boost"

PHONETIC_PLUGIN = "analysis-phonetic"

BUNDLED_SYNONYMS_FILE = Path(__file__).parent / "synonyms.txt"

# Written by the library, not supplied by the caller, so they are not part of
# `schemas.PAYLOAD_FIELDS`.
METADATA_FIELDS = frozenset(
    {
        "reference_pk",
        "dataset_id",
        "business_area",
        "program_code",
        "status",
    }
)


def index_name(business_area: str, program_code: str) -> str:
    """Return the index name for one business area and program.

    One index per `BiographicGroup`, which is why both components are in the name.
    Mirrors HOPE, which names its own per-program indices
    `{prefix}individuals_{business_area.slug}_{program.code}` - a short human-readable
    code, not a surrogate key, so the index list stays legible in `_cat/indices`.
    """
    return f"{settings.ELASTICSEARCH_PREFIX}biographic_{business_area}_{program_code}"


def index_pattern() -> str:
    """Match every biographic index this deployment owns."""
    return f"{settings.ELASTICSEARCH_PREFIX}biographic_*"


def load_synonyms() -> list[str]:
    """Read the synonyms driving nickname equivalence (Bill/William) on `given_name`."""
    configured = settings.ELASTICSEARCH_SYNONYMS_FILE
    path = Path(configured) if configured else BUNDLED_SYNONYMS_FILE
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def index_settings() -> dict[str, Any]:
    return {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "similarity": {
            "default": {
                "type": "scripted",
                "script": {"source": SIMILARITY_SCRIPT},
            },
        },
        "analysis": {
            "filter": {
                # HOPE passes `langauge_set` here, a typo Elasticsearch ignores.
                # Dropped rather than copied; scores are unaffected.
                "my_metaphone": {
                    "type": "phonetic",
                    "encoder": "double_metaphone",
                    "replace": False,
                },
                "synonym_tokenfilter": {
                    "type": "synonym",
                    "synonyms": load_synonyms(),
                },
            },
            "analyzer": {
                "phonetic": {
                    "tokenizer": "standard",
                    "filter": ["lowercase", "my_metaphone"],
                },
                "text_analyzer": {
                    "tokenizer": "standard",
                    "filter": ["lowercase", "synonym_tokenfilter"],
                },
            },
        },
    }


def index_mapping() -> dict[str, Any]:
    """Return the mapping.

    `similarity: boolean` fields are pure exact match: they score `1 * boost`, or
    nothing at all.
    """
    return {
        "properties": {
            "reference_pk": {"type": "keyword"},
            "dataset_id": {"type": "long"},
            "business_area": {"type": "keyword", "similarity": "boolean"},
            "program_code": {"type": "keyword"},
            "status": {"type": "keyword"},
            "given_name": {
                "type": "text",
                "analyzer": "text_analyzer",
                "fields": {"phonetic": {"type": "text", "analyzer": "phonetic"}},
            },
            "family_name": {
                "type": "text",
                "fields": {"phonetic": {"type": "text", "analyzer": "phonetic"}},
            },
            "full_name": {"type": "text", "analyzer": "phonetic"},
            "middle_name": {"type": "text", "analyzer": "phonetic"},
            "birth_date": {"type": "date"},
            "phone_no": {"type": "keyword", "similarity": "boolean"},
            "phone_no_alternative": {"type": "keyword", "similarity": "boolean"},
            "sex": {"type": "keyword"},
            "relationship": {"type": "keyword"},
        },
    }


def scoreable_fields() -> set[str]:
    """Return the properties a caller supplies, which must equal `schemas.PAYLOAD_FIELDS`."""
    return set(index_mapping()["properties"]) - set(METADATA_FIELDS)


def document_id(dataset_id: int, reference_pk: str) -> str:
    return f"{dataset_id}:{reference_pk}"


def to_document(
    payload: schemas.BiographicPayload,
    business_area: str,
    program_code: str,
    dataset_id: int,
    status: str = "pending",
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "reference_pk": payload.reference_pk,
        "dataset_id": dataset_id,
        "business_area": business_area,
        "program_code": program_code,
        "status": status,
    }
    for field in schemas.PAYLOAD_FIELDS:
        document[field] = getattr(payload, field)
    return document
