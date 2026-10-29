# Operations and Troubleshooting

Day-to-day tasks and diagnosis, mostly through `Home › Biographic` in the admin panel.

## Inspecting a set

    Home › Biographic › Biographic sets › <set>

The change form shows the state, the `error` of the last failed run, the notification settings, `search_sync_pending`, and the `log`: one entry per run with timestamp, final state, config, records indexed, findings created, records truncated by `max_hits`, the outcome of each notification, and the traceback on failure.

The list can be filtered by state and by `search_sync_pending`, and shows whether the program is locked. Related pages: **Biographic records** (search by name or `reference_pk`), **Biographic findings**, **Biographic groups** (settings, lock), **Biographic jobs** (runs and progress).

## Following a run

    Home › Biographic › Biographic jobs

Each `process` call creates a job showing its progress (records scored out of the total). Celery task results are in `Home › Celery Results › Task results`, and in [Flower](https://flower.readthedocs.io/) if deployed. A run ending in error appears as `FAILURE`, a cancelled one as `REVOKED`.

## Retrying a failed run

The client retries by calling `POST .../process/` on the `failed` set. The new run discards the old findings and overwrites the indexed documents.

!!! info "There is no Queue button on jobs"
    celery-boost's **Queue** button is disabled for biographic jobs: re-queueing skips the state check and the lock, and would rewrite a decided set's documents as `pending`. Start runs through the API, or the *Index records* and *Find duplicates* buttons on the set.

## Indexing and searching from the admin

An administrator can run the two halves of a run separately, from the buttons on a set. Both start a normal job, take the program's lock and follow the usual rules (one active set per program), so they appear in **Biographic jobs** like any run.

- **Index records** (visible in `pending` and `failed`) writes the set's records to the program's index and stops at `indexed`. Nothing is scored. Needs *Can index records*.
- **Find duplicates** (visible in `indexed` and `deduplicated`) scores the set against the index as it is, without indexing it again, and ends `deduplicated`. Its old findings are replaced. If the program's index is gone it fails the set and says so; rebuild the index first. Needs *Can find duplicates*.

An `indexed` set holds the program's slot like any active set. The API cannot move it on (`process` refuses `indexed`), so finish it with **Find duplicates**, or use *Mark as failed* to hand it back to the client.

## Rebuilding the index

A program's index lives only in Elasticsearch. If it is lost, restore the sets Postgres knows from their stored records:

- **Rebuild index** on a *group* restores every set that was indexed and is still alive.
- **Rebuild index** on a *set* (visible in `indexed`, `deduplicating`, `deduplicated`, `approved`) restores that set only.

Approved sets come back as `approved`, sets awaiting a decision as `pending`. Rejected, canceled, pending and failed sets have nothing to restore. The rebuild runs as a task and the program stays locked until it finishes; each restored set gets a `rebuild_index` entry in its log. Needs *Can rebuild index*.

A rebuild only adds documents. It never deletes or recreates the index, because HOPE puts documents of its own in program indexes (`dataset_id` 0) that Postgres does not hold. Document ids are `{set id}:{reference_pk}`, so running it again overwrites instead of duplicating. If an index was lost, documents HOPE had placed in it are lost too, and only HOPE can restore those.

Until an index with approved sets is rebuilt, `process` fails with "the index ... is missing" instead of searching an empty population.

## Stopping a run

On the job, the **Cancel** button asks the run to stop. The worker checks before every chunk, then fails the set with "Cancellation requested", logs it, notifies the client and releases the lock. The client can retry or cancel the set.

**Terminate** and **Revoke** kill the task without that cleanup: the set stays in `indexing`, `indexed` or `deduplicating` and the program stays locked. Recover with *Mark as failed* below.

## Recovering a stuck set

A worker killed hard (out of memory, node eviction) cannot run its cleanup. Symptoms: the set stays in a running state, and `process` for any set in the program returns 409. On the set:

- **Mark as failed** (visible in `indexing`, `indexed`, `deduplicating`) — sets `failed` with "Marked as failed by an administrator" and releases the program's lock. The client can then retry or cancel.
- **Unlock processing** (visible while the program is locked) — releases the lock only.

Check in Task results or Flower that no task is still running for the program first. Both buttons need the *Can release processing lock* permission.

## Decisions that have not reached Elasticsearch

Approve, reject and cancel-from-failed set `search_sync_pending` and queue `update_biographic_status`, which retries 5 times with backoff on connection errors. A set that keeps the flag (Elasticsearch was down for longer) needs no action: the next run in the program reconciles every flagged set before it searches. Filter the set list by `search_sync_pending` to see them.

## Rejected documents cleanup

    Home › Periodic Tasks › Periodic tasks › Biographic: delete rejected documents

Runs daily at 02:00 UTC and deletes `rejected` documents (rejected and canceled sets) from every index with this deployment's prefix. `approved` and `pending` documents are never touched, and it needs no lock. The deleted count per index is logged and returned as the task result.

Documents of a set that failed and was never retried or cancelled stay `pending` in the index. They are never searched by another set, so this is hygiene only; cancelling the set lets the cleanup remove them.

## Notifications

**Send notification** on a set pings its `notification_url` immediately, even when `notify` is off, and reports the result as a message. Needs the *Can send notification* permission.

## Common issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Run fails with "ELASTICSEARCH_HOST is not set" | Variable missing on the worker | Set it; see [Environment](environment.md). |
| Run fails with a missing `analysis-phonetic` plugin error | Plugin not installed on the cluster | Install it on every node and restart; see [Deployment](deployment.md). |
| `process` always returns 409 "Another task is already running" | Stale lock after a killed worker | See [Recovering a stuck set](#recovering-a-stuck-set). |
| `process` returns 409 "Another set ... awaiting approval" | A set in the program is `deduplicated` | The client must approve or reject it first. |
| Run fails with a `BulkIndexError` | The cluster refused writes (closed or read-only index, full disk) | Check cluster health and disk watermarks, then retry. |
| Run fails with `SearchItemError` | One search in an msearch failed on the cluster | The error names the reason; check the cluster logs. |
| Same full name pairs everywhere | Expected with the default 6.0 threshold, worse for large synonym groups | Raise the program's `duplicate_score`; see [Scoring](../concepts/pipeline.md). |
| Notifications not arriving | `notify` off, or the URL unreachable | Check the set and its log; failures go to Sentry. |
| 403 on every call | Token without the Api Biographic grant | Edit the token. |

## Sentry

Unhandled run errors and notification delivery failures are captured when `SENTRY_DSN` is set. The set's `error` holds a truncated message and the log holds the traceback.
