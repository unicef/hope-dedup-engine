# Getting Started

Two ways to develop locally: **Docker Compose** (recommended — everything included, matches production closely) or a **native virtualenv** (faster iteration, needs local PostgreSQL/Redis).

## Requirements

- [uv](https://docs.astral.sh/uv/) — package and environment manager
- [direnv](https://direnv.net/) — per-directory environment variables (native setup)
- Docker + Docker Compose (compose setup)
- Python 3.12 (managed by uv; the project pins `>=3.12,<3.13`)

## Option A: Docker Compose (recommended)

The repository's `compose.yml` starts the full stack — backend, Celery worker, Celery beat, Flower, PostgreSQL, Redis, and Azurite (local Azure blob emulator). It reads all environment configuration from a `.env` file (gitignored) next to `compose.yml`:

```console
$ cp env.sample .env    # then fill in the values (see below)
$ docker compose up --build
```

On startup the backend seeds demo data, applies migrations, and serves at [http://localhost:8000](http://localhost:8000). The admin panel is at `/admin/` (credentials `ADMIN_EMAIL` / `ADMIN_PASSWORD` from your `.env`), the API docs at `/api/rest/swagger/`.

### Configuration

`env.sample` lists every required key; `.env` is never committed, so real tokens and connection strings are safe there. This configuration works with the compose stack as-is (Azurite for blob storages, local filesystem for uploaded images):

```bash
# ── Django core ──────────────────────────────────────────────
ADMIN_EMAIL=adm@hde.org
ADMIN_PASSWORD=123
ALLOWED_HOSTS=localhost,127.0.0.1
SECRET_KEY=very-secret-key
DJANGO_SETTINGS_MODULE=hope_dedup_engine.config.settings
PYTHONPATH=/app/src

# ── Database / cache / broker ────────────────────────────────
DATABASE_URL=postgres://hde:password@db:5432/hope_dedupe_engine
CACHE_URL=redis://redis:6379/1
CELERY_BROKER_URL=redis://redis:6379/9
CELERY_TASK_ALWAYS_EAGER=False

# ── Security (local dev — all disabled) ──────────────────────
CSRF_COOKIE_SECURE=False
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_DOMAIN=
SESSION_COOKIE_SECURE=False
SOCIAL_AUTH_REDIRECT_IS_HTTPS=False

# ── File storage backends ────────────────────────────────────
FILE_STORAGE_DEFAULT=django.core.files.storage.FileSystemStorage
FILE_STORAGE_IMAGES=django.core.files.storage.FileSystemStorage
FILE_STORAGE_DNN=storages.backends.azure_storage.AzureStorage?azure_container=dnn&overwrite_files=True&connection_string=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://azurite:10000/devstoreaccount1;
FILE_STORAGE_MEDIA=storages.backends.azure_storage.AzureStorage?azure_container=media&overwrite_files=True&connection_string=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://azurite:10000/devstoreaccount1;
FILE_STORAGE_STATIC=storages.backends.azure_storage.AzureStorage?azure_container=static&overwrite_files=True&custom_domain=localhost:10000/&connection_string=DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://azurite:10000/devstoreaccount1;

# ── Filesystem roots ─────────────────────────────────────────
DEFAULT_ROOT=/var/hope_dedupe_engine/default
IMAGES_ROOT=/var/data
MEDIA_ROOT=/var/hope_dedupe_engine/media
STATIC_ROOT=/var/hope_dedupe_engine/static

# ── ML models ────────────────────────────────────────────────
DEEPFACE_HOME=/var/run/app/deepface
OFIQ_DATA_DIR=/root/.ofiq/data

# ── Performance tuning ───────────────────────────────────────
OMP_NUM_THREADS=2
TF_NUM_INTRA_OP_THREADS=2
TF_NUM_INTER_OP_THREADS=2

# ── Integration ──────────────────────────────────────────────
HOPE_API_TOKEN=
```

(The `AccountKey` above is [Azurite's public well-known development key](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite#well-known-storage-account-and-key), not a secret.)

Compose-level knobs (volume paths and port bindings) can also be set in `.env`: `IMAGES_HOST_PATH` (host directory for uploaded images, default `./var/data`), `DB_PORT`, `REDIS_PORT`, `CELERY_CONCURRENCY`.

### Things to know

- The repo is bind-mounted into the containers, so code changes are picked up by `runserver` automatically. The Celery worker does **not** auto-reload — restart it after changing task code.
- Model weight files are mounted from `./weights` (DeepFace) and `./ofiq_omdels` (OFIQ). See the comments in `compose.yml` for debugging variants of the service commands (debugpy).
- Uploaded images are stored under `./var/data` on the host — the same directory is mounted into the backend and the workers, mirroring the shared storage mount used in production.
- Run any management command inside the stack with `docker compose run --rm backend django-admin <command>`.

## Option B: Native virtualenv

```console
$ git clone https://github.com/unicef/hope-dedup-engine.git
$ cd hope-dedup-engine
$ uv venv .venv
$ uv sync

$ ./manage.py env --develop > .envrc   # generate development configuration
$ direnv allow .                        # load it
$ createdb hope_dedup_engine            # PostgreSQL database on localhost
```

You still need PostgreSQL and Redis running locally (adjust `DATABASE_URL` / `CACHE_URL` / `CELERY_BROKER_URL` in `.envrc` if they are not on default ports). Then:

```console
$ ./manage.py upgrade      # migrations, static files, superuser
$ ./manage.py runserver
```

and in separate terminals, when you need background processing:

```console
$ celery -A hope_dedup_engine.config.celery worker -E --loglevel=INFO --concurrency=2
$ celery -A hope_dedup_engine.config.celery beat --loglevel=INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

!!! note "Model weights"
    Face processing needs pre-trained model files under `DEEPFACE_HOME`. DeepFace downloads them automatically on first use. Without them (and without network access), only non-processing parts of the app will work.

## Pre-commit hooks

Linting is enforced with [pre-commit](https://pre-commit.com/) (ruff and friends):

```console
$ uv run pre-commit install
$ uv run pre-commit run --all-files   # run manually
```

## Working with the docs

The documentation is an MkDocs Material site living in `docs/`:

```console
$ uv sync --group docs
$ uv run mkdocs serve   # http://127.0.0.1:8001
```

Alternatively, serve them from the compose stack (port 8012): `docker compose --profile docs up docs`.

## Typical feature workflow

1. Create a branch from `develop`.
2. Make changes; if models change, generate a migration: `./manage.py makemigrations api`.
3. Add or update tests under `tests/` (see [Testing](testing.md)).
4. Run `uv run pytest tests` and `uv run pre-commit run --all-files`.
5. Open a pull request (see [Contributing](contributing.md)).
