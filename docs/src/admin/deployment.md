# Deployment

This guide is for operators deploying and configuring a HOPE Deduplication Engine instance.

## Prerequisites

The application is distributed as a Docker image on [Docker Hub](https://hub.docker.com/r/unicef/hope-dedup-engine/). A deployment consists of the same image running in several roles, plus backing services:

- **PostgreSQL 14+** — application database.
- **Redis** — cache and Celery broker.
- **Application containers** (one image, different commands):
    - `run` — web server (API + admin panel)
    - `worker` — Celery worker(s); CPU-intensive, scale these for throughput
    - `beat` — Celery scheduler (exactly one)

## First deployment

### 1. Configure the environment

All configuration is via environment variables — see the [environment reference](environment.md). To inspect what the image expects:

```console
$ docker run -it -t unicef/hope-dedup-engine:<tag> django-admin env         # show current configuration
$ docker run -it -t unicef/hope-dedup-engine:<tag> django-admin env --check # verify required variables
```

### 2. Run the setup

Runs deploy checks and applies database migrations:

```console
$ docker run -it -t <env...> unicef/hope-dedup-engine:<tag> setup
```

This also creates the initial superuser from `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

!!! note "Model weights"
    Face recognition models need pre-trained weight files under `DEEPFACE_HOME`. These are downloaded automatically on first use by DeepFace. `DEEPFACE_HOME` must be a volume shared between containers (writable for the backend, read-only is sufficient for the Celery workers). OFIQ model data is looked up under `OFIQ_DATA_DIR` and ships with the image.

### 3. Start the services

```console
$ docker run -d -t <env...> unicef/hope-dedup-engine:<tag> run
$ docker run -d -t <env...> unicef/hope-dedup-engine:<tag> worker
$ docker run -d -t <env...> unicef/hope-dedup-engine:<tag> beat
```

The web container serves the admin panel at `/admin/` (log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`) and the API documentation at `/api/rest/swagger/`. A health check endpoint is available at `/healthcheck`.

## Creating API credentials

Client systems authenticate with tokens scoped to an external *System*. To onboard a client (e.g. HOPE Country Workspace):

1. **Create the system** — `Home › Security › Systems` → add, e.g. "HOPE".
2. **Create a user** for the integration — `Home › Security › Users`. Grant it the *Can use api* permission (directly or via a group).
3. **Link the user to the system** — `Home › Security › User roles` → add a role connecting user, system, and group.
4. **Create the token** — `Home › Api › Tokens` → add, selecting the user and the system. The generated key is what the client sends as `Authorization: Token <key>`.

!!! warning "The system link is mandatory"
    A token whose user is not linked to a system cannot access any data — all API queries are filtered by the token's system.

## Outbound notifications

If clients use webhook notifications, the engine calls their `notification_url` with an `Authorization: Token <HOPE_API_TOKEN>` header. Set the `HOPE_API_TOKEN` value either via the environment variable or at `Home › Constance › Config`.

## Error monitoring

Set `SENTRY_DSN` (and optionally `SENTRY_ENVIRONMENT`) to enable [Sentry](https://sentry.io/) error reporting. Processing errors, notification delivery failures, and unhandled exceptions are captured there.
