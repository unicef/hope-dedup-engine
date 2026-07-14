# Getting Started

Two ways to develop locally: **Docker Compose** (recommended — everything included, matches production closely) or a **native virtualenv** (faster iteration, needs local PostgreSQL/Redis).

## Requirements

- [uv](https://docs.astral.sh/uv/) — package and environment manager
- [direnv](https://direnv.net/) — per-directory environment variables (native setup)
- Docker + Docker Compose (compose setup)
- Python 3.12 (managed by uv; the project pins `>=3.12,<3.13`)

## Option A: Docker Compose (recommended)

The repository's `compose.yml` starts the full stack — backend, Celery worker, Celery beat, Flower, PostgreSQL, and Redis:

```console
$ docker compose up --build
```

On startup the backend seeds demo data, applies migrations, and serves at [http://localhost:8000](http://localhost:8000). The admin panel is at `/admin/` (credentials from the compose environment: `adm@hde.org` / `123`), the API docs at `/api/rest/swagger/`.

Things to know:

- The repo is bind-mounted into the containers, so code changes are picked up by `runserver` automatically. The Celery worker does **not** auto-reload — restart it after changing task code.
- Model weight files are mounted from `./weights` (DeepFace) and `./ofiq_omdels` (OFIQ). See the comments in `compose.yml` for debugging variants of the service commands (debugpy).
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

## Typical feature workflow

1. Create a branch from `develop`.
2. Make changes; if models change, generate a migration: `./manage.py makemigrations api`.
3. Add or update tests under `tests/` (see [Testing](testing.md)).
4. Run `uv run pytest tests` and `uv run pre-commit run --all-files`.
5. Open a pull request (see [Contributing](contributing.md)).
