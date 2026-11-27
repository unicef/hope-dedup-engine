# Project Structure

Everything biographic is in one app, split into a service that owns the lifecycle and a search library that only talks to Elasticsearch.

```
src/hope_dedup_engine/apps/biographic/
├── models.py          # BiographicGroup, BiographicSet (state machine), BiographicRecord,
│                      # BiographicFinding, BiographicJob
├── schemas.py         # PAYLOAD_FIELDS, BiographicPayload, Hit: data crossing into the search library
├── protocols.py       # BiographicSearch: the interface the service calls (stable)
├── config.py          # BiographicConfig: the settings and how they are resolved
├── const.py           # Celery task and periodic task names
├── exceptions.py      # LifecycleConflictError and its subclasses InvalidTransitionError,
│                      # GroupDeletedError, GroupDeleteError (mapped to 409); IndexMissingError
├── services/
│   ├── lifecycle.py   # add_records, start_processing, cancel, decide: what a client can request
│   ├── process.py     # prepare, index, deduplicate, rebuild: processing and index recovery
│   └── status.py      # sync, reconcile: mirroring decisions into Elasticsearch
├── celery_tasks.py    # process_biographic_dataset, update_biographic_status,
│                      # rebuild_biographic_index, cleanup_biographic_rejected
├── search/            # the Elasticsearch library; imports no models
│   ├── client.py      # connection, plugin check, index listing
│   ├── index.py       # group-PK index naming, HOPE-parity settings and mapping, documents
│   ├── query.py       # the search body (ported from HOPE's DeduplicateTask)
│   ├── backend.py     # ElasticsearchBiographicSearch, the BiographicSearch implementation;
│   │                  # SearchItemError, IndexMappingError
│   └── synonyms.txt   # bundled nickname synonyms
├── views.py, serializers.py, filters.py, urls.py   # the API under /api/biographic/
├── admin.py, forms.py # admin pages, the program settings form
└── migrations/        # 0004 creates the daily cleanup PeriodicTask
```

## The service

- `models.py` — read first. `BiographicSet.VALID_TRANSITIONS`, `ACTIVE_STATES` and the `unique_active_biographic_set_per_group` constraint are the lifecycle; the [lifecycle](../concepts/lifecycle.md) and [data model](../concepts/data-model.md) pages describe them.
- `services/lifecycle.py` — every client action, with its checks and rollback. Raises domain errors, never HTTP ones, so the rules hold for views, admin and tests alike.
- `celery_tasks.py` — the biometric `find_duplicates` skeleton around `services/process.py`: state changes, notifications, run log, Sentry, and releasing the lock in `finally`.
- `config.py` — the single source of tunable settings. Field metadata (`kind`, `min_value`, `help_text`) drives the per-run override serializer and the admin form; adding a setting here, and its `DEFAULT_BIOGRAPHIC_*` key in `config/fragments/constance.py`, is all it takes.

## The search library

`search/` implements `protocols.BiographicSearch` and knows nothing of Django models. `index.py` preserves HOPE's scoring-critical index settings, analyzers and field mapping (`hope/apps/household/documents.py`), but names each index by the internal `BiographicGroup.pk`: `{ELASTICSEARCH_PREFIX}biographic_{group_id}`. `query.py` ports HOPE's search logic (`hope/apps/registration_data/tasks/deduplicate.py`). The service passes `group.pk` to the search backend; the external REST API continues to use business area and program code.

## Conventions

- **Postgres decides, Elasticsearch follows.** A decision commits its state and `search_sync_pending` together, then queues the status update; never write a status to Elasticsearch without the flag.
- **State changes** go through `BiographicSet.transition()` (row-locked check, used by client actions) or `set_state()` (validated against `VALID_TRANSITIONS`, used by the task). Don't assign `state` directly.
- **The protocol and schemas are stable.** `protocols.py` and `schemas.py` are shared between the service and search work; changing them needs the agreement of everyone working on biographic deduplication.
- **`PAYLOAD_FIELDS` is the only list of payload fields.** The serializer, the mapping and the query are tested against it.
- **Scoring is HOPE's.** Don't change the similarity script, analyzers, mapping types or query without re-running the parity tests and agreeing that the threshold must be recalibrated.
- **Program scoping**: dataset and findings API querysets go through `BiographicProgramMixin.program_sets()`, which excludes deleted groups. Each group has its own Elasticsearch index, so recreating a program never searches the deleted group's population.
- **Migrations**: `./manage.py makemigrations biographic`.
