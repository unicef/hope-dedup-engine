# Deployment

Biographic deduplication runs in the same containers as the rest of the engine (see the main [deployment guide](../../admin/deployment.md)). It adds one backing service and one requirement on the existing ones.

## Prerequisites

- **Elasticsearch 9** — a cluster dedicated to biographic deduplication, separate from HOPE's. The local stack uses 9.5.4; HOPE runs 9.4.2, and the parity tests keep the scores comparable.
- **The `analysis-phonetic` plugin** on every node. The phonetic name matching cannot be built without it. The engine checks for it before creating an index and fails the run with an explicit error if it is missing.
- **Celery beat** running, for the daily cleanup of rejected documents.

Installing the plugin on the official image:

```console
$ bin/elasticsearch-plugin install analysis-phonetic --batch
```

The repository's `compose.yml` has an `elasticsearch` service that does this on start.

## Configuration

Point the engine at the cluster with `ELASTICSEARCH_HOST`, and set `ELASTICSEARCH_PREFIX` if several environments share one cluster. See [Environment](environment.md).

Indices are normally created by the worker on a group's first processing run; **Rebuild index** in Django Admin can also create a missing index. There is nothing to create by hand. Each `BiographicGroup` has its own index, `{ELASTICSEARCH_PREFIX}biographic_{group_id}`, where `group_id` is the group's internal PostgreSQL PK. The REST API still identifies a program by business area and program code; clients do not need the group PK. Each index has **1 shard and 0 replicas**: HOPE's scoring is calibrated on a single shard.

Soft-deleting a group does not remove its index. Registering the same program again creates a new group with an empty population; its index is created on the first processing run. Old approved records cannot match new registrations. Physical cleanup of deleted groups and their indices is not implemented yet.

!!! warning "Recovering a missing index"
    PostgreSQL keeps the records and decisions used to build the searchable population. If an index is missing and the group has approved sets, processing refuses to create an empty index rather than silently miss those people. Use **Rebuild index** on the group in Django Admin to restore its approved and other indexed sets. The rebuild is additive and does not remove existing documents; rejected, canceled, pending and failed sets are not restored. On a multi-node cluster, use snapshots for faster recovery, or add replicas after creation (`PUT <index>/_settings {"number_of_replicas": 1}`), which does not change scores.

## Migrations

`setup` applies the biographic migrations with the rest. One of them creates the periodic task *Biographic: delete rejected documents*, daily at 02:00 UTC on the `queue_hde` queue.

## Creating API credentials

Biographic clients use `hope_api_auth` tokens with a grant:

1. **Create a user** for the integration — `Home › Security › Users`.
2. **Create the token** — `Home › Hope_Api_Auth › Api tokens` → add, select the user, tick the **Api Biographic** grant, optionally set `valid_to`.
3. Give the generated key to the client, which sends it as `Authorization: Token <key>`.

!!! warning "Grants are global"
    The grant opens every business area and program on the server. A superuser's token passes every grant check.

Every `POST` made with a token is recorded in `Home › Hope_Api_Auth › Api log entries`.
