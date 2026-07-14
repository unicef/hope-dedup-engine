# Architecture

The HOPE Deduplication Engine is a Django application with a REST API, an admin panel, and asynchronous Celery workers.

```mermaid
flowchart LR
    subgraph clients["Client systems"]
        cw["HOPE Country Workspace /<br>other external systems"]
    end

    subgraph hde["HOPE Deduplication Engine"]
        api["REST API<br>(Django + DRF)"]
        adminp["Admin panel"]
        db[("PostgreSQL")]
        redis[("Redis<br>cache + broker")]
        worker["Celery worker(s)<br>DeepFace + OFIQ"]
        beat["Celery beat"]
        images[("Image storage<br>(FILE_STORAGE_IMAGES)")]
    end

    cw -- "token-authenticated<br>REST calls" --> api
    api -- "webhook notification<br>(notification_url)" --> cw
    api --> db
    api -- "store images" --> images
    api -- "queue jobs" --> redis
    redis --> worker
    worker --> db
    worker -- "read images" --> images
    beat --> redis
    adminp --> db
```

## Components

- **REST API** — the only interface for client systems. Endpoints cover deduplication sets, image registration, processing, findings, group configuration, and group status. Interactive documentation is served by the application itself at `/api/rest/swagger/` and `/api/rest/redoc/`.
- **Admin panel** (`/admin/`) — used by administrators to manage external systems, API tokens, global default settings ([Constance](https://django-constance.readthedocs.io/)), per-group settings, and to inspect or re-queue processing jobs.
- **PostgreSQL** — stores all metadata: groups, deduplication sets, encodings (including face embeddings as float arrays), findings, and job records.
- **Redis** — Django cache and Celery broker.
- **Celery worker(s)** — run the face pipeline: image quality assessment (OFIQ), face detection and encoding (DeepFace), and duplicate search over the embeddings. This is CPU-heavy; concurrency and thread pools are tuned via environment variables (`OMP_NUM_THREADS`, `TF_NUM_INTRA_OP_THREADS`, `TF_NUM_INTER_OP_THREADS`).
- **Celery beat** — schedules periodic tasks.
- **Image storage** — configured via `FILE_STORAGE_IMAGES`, stores the uploaded image files. Can be local filesystem (default for development) or an object store backend (e.g. Azure Blob Storage). Images are stored under `images/{group_reference_pk}/{deduplication_set_id}/{filename}`.

## Key design points

- **Images are uploaded as base64 data URLs.** The API accepts a `filename` field containing a base64-encoded image (`data:<mimetype>;base64,...`). The engine decodes it, stores the file via the `images` Django storage backend, and reads it back when processing.
- **Everything asynchronous happens through jobs.** The `process` endpoint creates a `MainJob` and queues a Celery task. Clients follow progress via the set's `state` (polling) or via webhook notifications.
- **Multi-tenancy through Systems.** Every API token belongs to a user linked to an external *System*. All data is partitioned by system: a client can only see groups and sets belonging to its own system.
- **One active set per group.** A group (e.g. a HOPE program) can have only one deduplication set "in flight" at a time; previously approved sets stay in the group and are used as reference data for future runs. See [Lifecycle](lifecycle.md).
