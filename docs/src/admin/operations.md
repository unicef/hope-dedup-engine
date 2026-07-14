# Operations and Troubleshooting

Day-to-day tasks and diagnosing problems, mostly through the admin panel.

## Inspecting a deduplication set

    Home › Api › Deduplication sets › <set>

The set detail shows the current lifecycle state, the `error` field (populated when a run fails, with the traceback truncated), and the `log` — an append-only JSON audit of every processing run with timestamp, action (encode/deduplicate), the config snapshot used, counts of encodings processed and findings created, and any error.

Related admin pages: **Encodings** (per-image records with embedding status and cached quality scores), **Findings** (results), **Deduplication set groups** (settings, processing lock).

## Re-running processing

If a run failed, or a set should be re-processed after changes:

1. Navigate to `Home › Api › Dedup jobs` (or the *jobs* section on the set).
2. Select the job for the deduplication set.
3. Use the **Queue** button to re-queue it.

Alternatively the client system can simply call `POST /deduplication_sets/{id}/process/` again — retry is allowed from the failed states.

Celery task execution can be monitored at:

    Home › Celery Results › Task results

and, if deployed, in [Flower](https://flower.readthedocs.io/) (`celery-flower` service).

## Releasing a stuck processing lock

Each group has a `processing_locked` flag preventing concurrent runs. The worker releases it in a `finally` block, so it should clear even on failure — but if a worker was killed hard (OOM, node eviction) the flag can remain set, and all `process` calls for the group will return 409. Check the group in `Home › Api › Deduplication set groups` and clear the flag if no task is actually running (verify in Task results / Flower first).

## Common issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| All findings have status 404 | Wrong `FILE_STORAGE_IMAGES` configuration, or image files missing from storage | Verify the storage configuration and that registered images exist at the expected paths. |
| `process` always returns 409 "another task is already running" | Stale processing lock | See [releasing a stuck lock](#releasing-a-stuck-processing-lock). |
| Encoding fails instantly | Missing model weights | Check the `DEEPFACE_HOME` volume is mounted and writable (weights are auto-downloaded on first use). |
| Quality checks fail unexpectedly / OFIQ errors | OFIQ model data missing | Check `OFIQ_DATA_DIR` contents. |
| Webhooks not arriving at the client | `notify=false` on the set, client URL unreachable, or missing `HOPE_API_TOKEN` on their side | Check the set's `notify`/`notification_url`; delivery failures are reported to Sentry. |
| API token rejected (401/403) | Token's user not linked to a System, or missing *Can use api* permission | See [creating API credentials](deployment.md#creating-api-credentials). |

## Sentry

All unhandled processing errors, per-image generic errors, and webhook delivery failures are captured by Sentry when `SENTRY_DSN` is configured. The set's `error` field only holds a truncated message — the full traceback is in Sentry.
