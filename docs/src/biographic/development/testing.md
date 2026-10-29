# Testing

Biographic tests live in `tests/apps/biographic/`. Most of them run against an in-memory fake of the search library; the ones that check real scores need an Elasticsearch cluster and skip themselves without one.

## Running tests

```console
$ uv run pytest tests/apps/biographic                 # everything biographic
$ uv run pytest tests/apps/biographic -m elasticsearch # only the tests needing a cluster
$ uv run pytest tests/apps/biographic -m "not elasticsearch"
```

For the cluster tests, start the compose service, which installs `analysis-phonetic`:

```console
$ docker compose up -d elasticsearch
```

They connect to `ELASTICSEARCH_HOST` (default `http://localhost:9200`), use a test index prefix, and are skipped with a message when the cluster is unreachable or lacks the plugin.

## What is where

| File | Covers | Needs a cluster |
|------|--------|-----------------|
| `test_biographic_models.py` | state machine, transitions, constraints, jobs | no |
| `test_biographic_lifecycle.py` | client actions, locks, rollbacks, status queueing | no |
| `test_biographic_api.py`, `test_biographic_serializers.py` | endpoints, validation, counts, auth | no |
| `test_biographic_process.py` | prepare, index, deduplicate against the fake | no |
| `test_biographic_tasks.py` | the Celery tasks: full run, failures, retry, cancellation, cleanup, the periodic task | no |
| `test_biographic_status.py` | sync and reconcile | no |
| `test_biographic_config.py`, `test_biographic_forms.py`, `test_biographic_admin.py` | settings resolution, the settings form, admin pages and buttons | no |
| `test_query.py`, `test_client.py`, `test_protocols.py` | query bodies, client helpers (mocked), protocol conformance | no |
| `test_index.py` | index name, settings, mapping, documents; one test creates a real index | the last test only |
| `test_search.py` | the backend against a real cluster, including `search_many` = `search` | yes |
| `test_parity.py` | known HOPE scores stay on the same side of the thresholds | yes |

## The fake search backend

`tests/extras/testutils/biographic.py` provides `FakeBiographicSearch`, an in-memory implementation of `BiographicSearch` with HOPE's candidate rules (pending in the same set, or approved; never one's own `reference_pk`). It matches on a case-insensitive full name with a fixed score, can be told to fail on a given call, and records every call. The `fake_search` fixture installs it in the Celery tasks.

Other fixtures in `tests/apps/biographic/conftest.py`: `queued_tasks` and `queued_jobs` capture what would be sent to the broker, `no_tracking` stubs celery-boost's Redis tracking, `sent_notifications` captures notifications.

## Notes

- `test_protocols.py` checks the protocol's method list, that the real backend's signatures match it, and that the fake takes the same parameters, so a protocol change fails fast on both sides.
- Changing anything in `search/index.py` or `search/query.py` must keep `test_parity.py` green; it is what ties these scores to HOPE's.
