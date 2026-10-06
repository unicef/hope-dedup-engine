"""Implementation of the `BiographicSearch` protocol.

The whole public surface of this library. It indexes records, searches them with
HOPE's scoring, and maintains their lifecycle status. It has no opinion on what a
duplicate is: it returns scored hits, and the service classifies them.
"""

from typing import Any

from elasticsearch import BadRequestError, Elasticsearch
from elasticsearch.helpers import bulk

from hope_dedup_engine.apps.biographic import schemas
from hope_dedup_engine.apps.biographic.search import client, index, query

INDEX_EXISTS_ERROR = "resource_already_exists_exception"

SET_STATUS_SCRIPT = "ctx._source.status = params.status"


class ElasticsearchBiographicSearch:
    def __init__(self, es_client: Elasticsearch | None = None) -> None:
        self._client = es_client

    @property
    def client(self) -> Elasticsearch:
        if self._client is None:
            self._client = client.get_client()
        return self._client

    def ensure_index(self, business_area: str, program_code: str) -> str:
        """Create the index for one business area and program if it is not there yet."""
        name = index.index_name(business_area, program_code)
        if self.client.indices.exists(index=name):
            return name

        client.verify_phonetic_plugin(self.client)
        try:
            self.client.indices.create(
                index=name,
                settings=index.index_settings(),
                mappings=index.index_mapping(),
            )
        except BadRequestError as error:
            # Another worker won the race. The index is there, which is all the
            # caller asked for.
            if error.error != INDEX_EXISTS_ERROR:
                raise
        return name

    def index_records(
        self,
        business_area: str,
        program_code: str,
        dataset_id: int,
        records: list[schemas.BiographicPayload],
    ) -> int:
        """Bulk index a dataset's records as `pending`. Returns the number indexed."""
        if not records:
            return 0

        name = index.index_name(business_area, program_code)
        actions = [
            {
                "_index": name,
                "_id": index.document_id(dataset_id, record.reference_pk),
                "_source": index.to_document(record, business_area, program_code, dataset_id),
            }
            for record in records
        ]
        indexed, _ = bulk(self.client, actions, chunk_size=client.BULK_CHUNK_SIZE)
        return indexed

    def refresh(self, business_area: str, program_code: str) -> None:
        """Make newly indexed documents searchable. HOPE's `ensure_index_ready`."""
        self.client.indices.refresh(index=index.index_name(business_area, program_code))

    def search(  # noqa: PLR0913, PLR0917 - signature fixed by the frozen contract
        self,
        business_area: str,
        program_code: str,
        payload: schemas.BiographicPayload,
        min_score: float,
        dataset_id: int,
        size: int = 100,
    ) -> list[schemas.Hit]:
        """Return scored matches for one record, best first.

        One search spans the caller's pending dataset and the approved
        population; each hit says which side it came from.
        """
        body = query.build_query(
            payload,
            min_score=min_score,
            dataset_id=dataset_id,
            size=size,
        )
        response = self.client.search(
            index=index.index_name(business_area, program_code),
            query=body["query"],
            size=body["size"],
            min_score=body["min_score"],
            # Consistent scoring across shards. We use one shard, so this is
            # belt and braces, but HOPE sets it and parity is the goal.
            search_type="dfs_query_then_fetch",
        )
        return [self._to_hit(hit) for hit in response["hits"]["hits"]]

    def set_status(
        self,
        business_area: str,
        program_code: str,
        dataset_id: int,
        status: str,
    ) -> int:
        """Move one dataset's documents to `status`. Returns the number updated."""
        response = self.client.update_by_query(
            index=index.index_name(business_area, program_code),
            query={"term": {"dataset_id": dataset_id}},
            script={
                "source": SET_STATUS_SCRIPT,
                "lang": "painless",
                "params": {"status": status},
            },
            conflicts="proceed",
            refresh=True,
        )
        return int(response["updated"])

    def delete_by_status(self, status: str) -> dict[str, int]:
        """Delete documents with `status` from every biographic index.

        Returns the deleted count per index. Documents in any other status are
        never touched. Cleanup runs across a wildcard because an explicit index
        list would mean enumerating groups, and this library does not import
        models.
        """
        deleted: dict[str, int] = {}
        for name in client.find_indices(self.client, index.index_pattern()):
            response = self.client.delete_by_query(
                index=name,
                query={"term": {"status": status}},
                conflicts="proceed",
                refresh=True,
            )
            deleted[name] = int(response["deleted"])
        return deleted

    @staticmethod
    def _to_hit(hit: dict[str, Any]) -> schemas.Hit:
        source = hit["_source"]
        return schemas.Hit(
            reference_pk=source["reference_pk"],
            score=hit["_score"],
            dataset_id=source["dataset_id"],
            status=source["status"],
            full_name=source.get("full_name"),
            birth_date=source.get("birth_date"),
        )
