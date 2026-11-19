# Operations and Troubleshooting

Day-to-day tasks and diagnosis, mostly through `Home › Biographic` in the admin panel.

## Inspecting a set

    Home › Biographic › Biographic sets › <set>

The change form shows the [state](../concepts/lifecycle.md#states), the `error` of the last failed run, the notification settings, `search_sync_pending`, and the `log`: one entry per run with timestamp, final state, config, records indexed, findings created, records truncated by `max_hits`, the outcome of each notification, and the traceback on failure.

The list can be filtered by state and by `search_sync_pending`, and shows whether the program is locked. Related pages: **Biographic records** (search by name or `reference_pk`), **Biographic findings**, **Biographic groups** ([settings](settings.md#per-program-settings), lock and recovery status), **Biographic jobs** (runs and progress). The group list also filters by the read-only `index_rebuild_required` flag; see [Rebuilding the index](#rebuilding-the-index).

## Following a run

    Home › Biographic › Biographic jobs

Each `process` call creates a job showing its progress (records scored out of the total). Celery task results are in `Home › Celery Results › Task results`, and in [Flower](https://flower.readthedocs.io/) if deployed. A run ending in error appears as `FAILURE`, a cancelled one as `REVOKED`. API clients can follow the set through [polling or notifications](../integration/notifications.md).

## Retrying a failed run

The client retries by calling `POST .../process/` on the `failed` set; see [Start processing](../integration/workflow.md#3-start-processing). Once [index readiness](#incomplete-rebuilds) checks pass, the new run discards the old findings and overwrites the indexed documents. If those checks fail, the previous findings remain stored.

!!! info "There is no Queue button on jobs"
    celery-boost's **Queue** button is disabled for biographic jobs: re-queueing skips the state check and the lock, and would rewrite a decided set's documents as `pending`. Start runs through the API, or the *Index records* and *Find duplicates* buttons on the set.

## Indexing and searching from the admin

An administrator can run the two halves of a run separately, from the buttons on a set. Both start a normal job, take the program's lock and follow the usual rules (one active set per program), so they appear in **Biographic jobs** like any run.

- **Index records** (visible in `pending` and `failed`) writes the set's records to the program's index and stops at `indexed`. Nothing is scored. Needs *Can index records*.
- **Find duplicates** (visible in `indexed` and `deduplicated`) scores the set against the index as it is, without indexing it again, and ends `deduplicated`. Its old findings are replaced. If the program's index is gone it fails the set and says so; [rebuild the group](#rebuilding-the-index) first. Needs *Can find duplicates*.

Both jobs apply the [index readiness checks](#incomplete-rebuilds) in the worker. An `indexed` set holds the [program's slot](../concepts/lifecycle.md#programs-one-active-set-at-a-time) like any active set. The API cannot move it on (`process` refuses `indexed`), so finish it with **Find duplicates**, or use [Mark as failed](#recovering-a-stuck-set) to hand it back to the client.

## Rebuilding the index

Each `BiographicGroup` has its own Elasticsearch index, named `{ELASTICSEARCH_PREFIX}biographic_{group_id}`. The group ID is internal to DedupEngine; API clients continue to identify the program by business area and program code. Rebuild restores documents from the records kept in Postgres:

| Action | Restores | Index requirements |
|--------|----------|--------------------|
| **Rebuild index** on a *group* | All eligible sets in the group | Creates the index if missing; can retry an unfinished full rebuild. |
| **Rebuild index** on a *set* | Only the selected eligible set | The index must exist and `index_rebuild_required` must be false. |

Approved sets come back as `approved`, and indexed, deduplicating and deduplicated sets as `pending`. Rejected, canceled, pending, indexing and failed sets are not restored. The set's button is visible only in restorable states. Both actions require [Can rebuild index](settings.md#permissions); a deleted group cannot start a rebuild.

Both actions run as tasks and take the program's processing lock. Follow their Celery task results as described in [Following a run](#following-a-run). After a successful rebuild, each restored set gets a `rebuild_index` entry in its log.

A rebuild is additive: it never deletes or empties an existing index. It restores only datasets belonging to that `BiographicGroup` from their records in Postgres. Document ids are `{dataset_id}:{reference_pk}`, so running it again overwrites documents rather than duplicating them. Soft-deleting a group leaves its index in place; creating a dataset for the same program registers a new group with a different PK and a separate, initially empty index. Physical cleanup of deleted groups and their indices is not implemented yet.

### Incomplete rebuilds

A full rebuild worker sets `index_rebuild_required` in Postgres before touching the index. It clears the flag only after all eligible sets have been written, the index refreshed and [pending decisions reconciled](#decisions-that-have-not-reached-elasticsearch). The flag records an unfinished full rebuild; `processing_locked` serializes processing and rebuilds.

If a full rebuild fails during index restoration, the task releases the processing lock but keeps the recovery flag. Fix the reported cause and use **Rebuild index** on the **group** again. If the worker was killed and the lock remains, follow [Recovering a stuck set](#recovering-a-stuck-set).

While recovery is required, processing, indexing and search jobs fail in the worker before replacing findings or writing/searching documents. An accepted API request or queued admin action does not mean the index is ready. A missing index also prevents processing when the group has approved sets; search-only jobs always require an existing index.

A successful group rebuild clears the recovery flag but does not change set states or rerun failed jobs. [Retry the failed set](#retrying-a-failed-run) afterwards.

### Incompatible index mappings

An incompatible mapping also prevents use of the index; for example, "Index ... maps `dataset_id` as long, not keyword". A `long` mapping cannot hold UUID dataset IDs, and Elasticsearch cannot change a field's type in place. A rebuild cannot fix it, because it never replaces an existing index. Delete the affected group's index in Elasticsearch, then use **Rebuild index** on that group to recreate it and restore the eligible datasets from Postgres.

## Stopping a run

On the job, the **Cancel** button asks the run to stop. The worker checks before every chunk, then fails the set with "Cancellation requested", logs it, notifies the client and releases the lock. The client can retry or cancel the set.

**Terminate** forcibly stops a running task (or removes one from the queue) without the worker's cleanup. **Revoke** prevents a queued task from starting; it does not stop a task that is already running. Either may leave the set in `indexing`, `indexed` or `deduplicating` and the program locked. Confirm the worker is no longer running the task, then use [Mark as failed](#recovering-a-stuck-set).

## Recovering a stuck set

A worker killed hard (out of memory, node eviction) cannot run its cleanup. Symptoms: the set stays in a running state, and `process` for any set in the program returns 409. On the set:

- **Mark as failed** (visible in `indexing`, `indexed`, `deduplicating`) — sets `failed` with "Marked as failed by an administrator" and releases the program's lock. The client can then retry or cancel.
- **Unlock processing** (visible while the program is locked) — releases the lock only; it does not clear `index_rebuild_required`.

Check in Task results or Flower that no task is still running for the program first. Both buttons need the [Can release processing lock](settings.md#permissions) permission.

For a killed rebuild, use **Unlock processing** on a set in the group, then [rebuild the group](#rebuilding-the-index). Rebuild does not change set states, so leave those states intact.

## Decisions that have not reached Elasticsearch

Approve, reject and cancel-from-failed set `search_sync_pending` and queue `update_biographic_status`, which retries 5 times with backoff on connection errors. A set that keeps the flag after Elasticsearch downtime is reconciled during the next run once the index passes readiness checks, or during a successful [group rebuild](#rebuilding-the-index). Filter the set list by `search_sync_pending` to see them.

## Rejected documents cleanup

    Home › Periodic Tasks › Periodic tasks › Biographic: delete rejected documents

Runs daily at 02:00 UTC and deletes `rejected` documents (rejected and canceled sets) from every index with this deployment's prefix. `approved` and `pending` documents are never touched, and it needs no lock. The deleted count per index is logged and returned as the task result.

Documents of a set that failed and was never retried or cancelled stay `pending` in the index. They are never searched by another set, so this is hygiene only; cancelling the set lets the cleanup remove them.

## Notifications

**Send notification** on a set pings its `notification_url` immediately, even when `notify` is off, and reports the result as a message. Needs the *Can send notification* permission; see [Webhook notifications](../integration/notifications.md#webhook-notifications) for the callback contract.

## Common issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Run fails with "ELASTICSEARCH_HOST is not set" | Variable missing on the worker | Set it; see [Environment](environment.md). |
| Run fails with a missing `analysis-phonetic` plugin error | Plugin not installed on the cluster | Install it on every node and restart; see [Deployment](deployment.md). |
| `process` always returns 409 "Another task is already running" | Stale lock after a killed worker | See [Recovering a stuck set](#recovering-a-stuck-set). |
| `process` returns 409 "Another set ... awaiting approval" | A set in the program is `deduplicated` | The client must approve or reject it first. |
| Run or set rebuild fails with a missing-index error | The group's index is absent | Use [Rebuild index on the group](#rebuilding-the-index). |
| Run or set rebuild fails with "requires a full rebuild" | A full group rebuild has not completed | Resolve the rebuild error, then [retry the group rebuild](#incomplete-rebuilds). |
| Run fails with a `BulkIndexError` | The cluster refused writes (closed or read-only index, full disk) | Check cluster health and disk watermarks, then retry. If a full rebuild failed, retry the [whole group](#incomplete-rebuilds). |
| Run fails with `SearchItemError` | One search in an msearch failed on the cluster | The error names the reason; check the cluster logs. |
| Same full name pairs everywhere | Expected with the default 6.0 threshold, worse for large synonym groups | Raise the program's `duplicate_score`; see [Scoring](../concepts/pipeline.md). |
| Notifications not arriving | `notify` off, or the URL unreachable | Check the set and its log; failures go to Sentry. |
| 403 on every call | Token without the Api Biographic grant | Edit the token. |

## Sentry

Unhandled run errors and notification delivery failures are captured when `SENTRY_DSN` is set. The set's `error` holds a truncated message and the log holds the traceback.
