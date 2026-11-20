# Sequence Diagrams

One small diagram per flow. Participants are named after the code: `lifecycle` is `services/lifecycle.py`, `process` is `services/process.py`, the task is `process_biographic_dataset` in `celery_tasks.py`.

## Create a set and upload people

```mermaid
sequenceDiagram
    participant C as Client
    participant API as DatasetViewSet
    participant L as lifecycle
    participant DB as Postgres

    C->>API: POST /datasets/ {notification_url, notify}
    API->>DB: get_or_create BiographicGroup (snapshot Constance settings)
    API->>DB: create BiographicSet (pending)
    API-->>C: 201 {dataset_id, status: pending}

    loop up to 10,000 records per call
        C->>API: POST /datasets/{id}/records/ {records}
        API->>L: add_records
        L->>DB: SELECT ... FOR UPDATE set, require pending
        L->>DB: bulk upsert records (same reference_pk replaces)
        API-->>C: 201 {received, records_count}
    end
```

## Start processing

The API queues the run; index readiness is checked later by the worker. See [Start processing](../integration/workflow.md#3-start-processing) for the request and response contract.

```mermaid
sequenceDiagram
    participant C as Client
    participant API as DatasetViewSet
    participant L as lifecycle
    participant DB as Postgres
    participant Q as Celery broker

    C->>API: POST /datasets/{id}/process/ {overrides?}
    API->>L: start_processing
    L->>DB: pending or failed? has records? no other active set?
    L->>DB: acquire_processing_lock (FOR UPDATE on group)
    break lock held
        L-->>API: LifecycleConflictError
        API-->>C: 409
    end
    L->>DB: one transaction: set -> indexing, create BiographicJob
    Note over DB: lost race: unique_active_biographic_set_per_group fires,<br>rollback, release lock, 409
    L->>Q: job.queue() -> process_biographic_dataset(job_id, version)
    break publish fails
        L->>DB: set -> failed (could not queue), release lock
        L-->>API: re-raise publish error
    end
    API->>DB: read current set state
    API-->>C: 200 {dataset_id, status}
```

## Worker run, happy path

The full run follows [Prepare](pipeline.md#stage-1-prepare). For index-only and search-only runs, see [admin indexing and searching](../admin/operations.md#indexing-and-searching-from-the-admin).

```mermaid
sequenceDiagram
    participant W as process_biographic_dataset
    participant P as process
    participant ES as Elasticsearch
    participant DB as Postgres
    participant H as notification_url

    W->>DB: load job, set, group
    W->>H: GET (indexing)
    W->>P: prepare
    P->>DB: require index_rebuild_required = false
    P->>ES: index_exists; check existing dataset_id and status mappings
    opt index is missing
        P->>DB: require no approved sets
    end
    P->>DB: delete this set's findings
    P->>ES: ensure_index
    P->>ES: reconcile pending decisions
    W->>P: index
    loop 2,000 records per bulk request
        P->>ES: index as pending
    end
    P->>ES: refresh
    W->>DB: set -> indexed
    W->>H: GET (indexed)
    W->>DB: set -> deduplicating
    W->>H: GET (deduplicating)
    W->>P: deduplicate
    W->>DB: set -> deduplicated
    W->>H: GET (deduplicated)
    W->>DB: append log entry
    W->>DB: release_processing_lock (finally)
```

## Scoring one chunk

```mermaid
sequenceDiagram
    participant P as process
    participant J as BiographicJob
    participant B as ES backend
    participant ES as Elasticsearch
    participant DB as Postgres

    P->>DB: next 200 records (pk > last pk)
    P->>J: ensure_not_cancelled
    P->>B: search_many(payloads, min_score=duplicate_score, size=max_hits)
    B->>ES: msearch, 200 HOPE queries, dfs_query_then_fetch
    ES-->>B: one response per search (a failed one raises SearchItemError)
    B-->>P: hits per record, best first
    P->>P: best hit per (reference_pk, scope),<br>batch if same set else population
    P->>DB: bulk_create findings
    P->>J: set_progress
```

## Failure and retry

Readiness failures leave previous findings stored. For a missing population index or an unfinished full rebuild, [rebuild the group](../admin/operations.md#incomplete-rebuilds) before retrying the failed set.

```mermaid
sequenceDiagram
    participant W as Task
    participant DB as Postgres
    participant H as notification_url
    participant C as Client
    participant API as DatasetViewSet

    W->>W: exception during preparation, indexing or scoring
    W->>DB: re-read set; if still running -> failed (error)
    W->>H: GET (failed)
    W->>DB: log entry with traceback
    W->>W: report to Sentry, re-raise (Celery FAILURE)
    W->>DB: release_processing_lock (finally)

    C->>API: POST /process/ again (set is failed)
    Note over C,API: new job; clear findings only after readiness checks pass
    Note over C,API: indexing overwrites the same document IDs
```

## Graceful cancellation from the admin

```mermaid
sequenceDiagram
    participant A as Admin
    participant R as Redis tracking
    participant W as Task
    participant DB as Postgres

    A->>R: job Cancel button -> terminate_requested = 1
    W->>R: ensure_not_cancelled (before each chunk)
    R-->>W: requested
    W->>W: raise GracefulJobCancellationError
    W->>DB: set -> failed ("Cancellation requested")
    W->>DB: log entry, job local_status = CANCELED
    W->>W: Celery state REVOKED, raise Ignore
    W->>DB: release_processing_lock (finally)
```

## Approve or reject, then mirror into Elasticsearch

```mermaid
sequenceDiagram
    participant C as Client
    participant L as lifecycle
    participant DB as Postgres
    participant Q as Celery status task
    participant ES as Elasticsearch

    C->>L: POST /approve/ (or /reject/)
    L->>DB: one transaction: FOR UPDATE, require deduplicated,<br>search_sync_pending = true, state -> approved / rejected
    L->>Q: send_task(update_biographic_status) (a failure is only logged)
    L-->>C: 200
    Q->>Q: run update_biographic_status (5 retries with backoff on connection errors)
    Q->>ES: update_by_query dataset_id -> approved / rejected
    opt status update succeeds
        Q->>DB: search_sync_pending = false
    end
```

## Reconcile at the start of the next run

During processing, reconciliation follows the readiness checks. It synchronizes [pending decisions](../admin/operations.md#decisions-that-have-not-reached-elasticsearch); it does not restore missing documents or clear the group's recovery flag.

```mermaid
sequenceDiagram
    participant W as Next run (prepare)
    participant DB as Postgres
    participant ES as Elasticsearch

    W->>DB: sets in the program with search_sync_pending
    loop each flagged set
        W->>ES: set_status (canceled counts as rejected)
        opt status update succeeds
            W->>DB: search_sync_pending = false
        end
    end
    Note over W,ES: search follows status reconciliation
```

## Cancel a pending or failed set

```mermaid
sequenceDiagram
    participant C as Client
    participant L as lifecycle
    participant DB as Postgres
    participant Q as Celery

    C->>L: POST /cancel/
    L->>DB: require pending or failed, state -> canceled
    alt was failed (may have indexed documents)
        L->>DB: search_sync_pending = true (same transaction)
        L->>Q: update_biographic_status -> documents rejected
    end
```

## Daily cleanup

```mermaid
sequenceDiagram
    participant B as Celery beat (02:00 UTC)
    participant T as cleanup_biographic_rejected
    participant ES as Elasticsearch

    B->>T: run
    T->>ES: list indices {prefix}biographic_*
    loop each index
        T->>ES: delete_by_query status = rejected
    end
    T-->>B: deleted count per index
```

## Reading results

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API
    participant DB as Postgres

    C->>API: GET /datasets/{id}/
    API->>DB: set + records_count + batch_duplicates + population_duplicates
    API-->>C: {status, error, counts, notification_url, notify}

    C->>API: GET /datasets/{id}/findings/?scope=&min_score=&reference_pk=&page=
    API->>DB: require deduplicated or approved, order by -score
    API-->>C: paginated findings, one per side
```

## Changing a program's thresholds

```mermaid
sequenceDiagram
    participant A as Admin
    participant F as BiographicGroupSettingsForm
    participant DB as Postgres
    participant W as Next run

    A->>F: edit duplicate_score / max_hits
    F->>DB: validate, write group.settings
    W->>DB: resolve_config: request override > group settings > Constance
    Note over W,DB: every finding stores the config it was scored with,<br>so earlier results keep their meaning
```
