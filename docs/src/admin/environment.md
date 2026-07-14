# Environment Variables

All runtime configuration is provided through environment variables, managed with [django-smart-env](https://pypi.org/project/django-smart-env/). The image itself can report its configuration:

```console
$ docker run -it -t unicef/hope-dedup-engine:<tag> django-admin env          # current values
$ docker run -it -t unicef/hope-dedup-engine:<tag> django-admin env --check  # verify required ones
```

An auto-generated reference of every known variable is on the [Settings](../settings.md) page; below are the ones that matter operationally, grouped by purpose.

## Required

### Core

| Variable | Example | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *(long random string)* | Django secret key. |
| `DATABASE_URL` | `postgres://user:pass@db:5432/hope_dedup_engine` | PostgreSQL connection URL. |
| `CACHE_URL` | `redis://redis:6379/1` | Redis cache URL. |
| `CELERY_BROKER_URL` | `redis://redis:6379/9` | Celery broker URL. |
| `ALLOWED_HOSTS` | `dedupe.example.org` | Comma-separated host names Django will serve. |
| `ADMIN_EMAIL` | `adm@example.org` | Initial superuser created at first deploy. |
| `ADMIN_PASSWORD` | *(secret)* | Password for the initial superuser. |
| `CSRF_COOKIE_SECURE` | `True` | Secure flag on the CSRF cookie (set `False` only for local HTTP). |

### File storage

Storage backends use the smart-env URL syntax: `<backend.class>?option=value&...`.

| Variable | Description |
|----------|-------------|
| `FILE_STORAGE_IMAGES` | Storage for uploaded image files. Defaults to `FileSystemStorage` (local); can be set to an object store (e.g. `storages.backends.azure_storage.AzureStorage?...`). |
| `FILE_STORAGE_STATIC` | Storage for static files (CSS/JS). |
| `FILE_STORAGE_MEDIA` | Storage for media files. |
| `FILE_STORAGE_DEFAULT` | Default Django storage; typically `django.core.files.storage.FileSystemStorage`. |

### Local directories

| Variable | Example | Description |
|----------|---------|-------------|
| `DEEPFACE_HOME` | `/var/run/app/deepface` | Where DeepFace model weights live (auto-downloaded on first use). Shared volume: writable for the backend, read-only for workers. |
| `IMAGES_ROOT` | `/var/data` | Root directory for image files when `FILE_STORAGE_IMAGES` uses `FileSystemStorage`. Images are stored under `images/{group}/{set}/{filename}`. |
| `DEFAULT_ROOT` | `/var/hope_dedupe_engine/default` | Root for locally stored files. |
| `MEDIA_ROOT` | `/var/hope_dedupe_engine/media` | Media files root. |
| `STATIC_ROOT` | `/var/hope_dedupe_engine/static` | Static files root. |

## Optional but recommended

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTRY_DSN` | *(empty — disabled)* | Sentry error reporting DSN. |
| `SENTRY_ENVIRONMENT` | `production` | Environment tag for Sentry events. |
| `HOPE_API_TOKEN` | *(empty)* | Token sent in the `Authorization` header of outbound webhook notifications. Can also be set via Constance. |
| `OFIQ_DATA_DIR` | `/root/.ofiq/data` | OFIQ model data directory. |
| `OMP_NUM_THREADS`, `TF_NUM_INTRA_OP_THREADS`, `TF_NUM_INTER_OP_THREADS` | *(unset)* | Thread-pool limits for OpenMP/TensorFlow — tune to avoid oversubscription when running multiple worker processes on one host. |
| `LOG_LEVEL` | `CRITICAL` | Root logging level. |
| `DEBUG` | `False` | Never enable in production. |
| `SUPERUSERS` | *(empty)* | Emails/usernames auto-granted superuser at first creation (CI/dev environments). |

## Azure AD login (admin panel SSO)

| Variable | Description |
|----------|-------------|
| `AZURE_TENANT_ID` | Azure AD tenant for social login. |
| `AZURE_CLIENT_ID` | OAuth application (client) ID. |
| `AZURE_CLIENT_SECRET` | OAuth client secret. |
| `LOGIN_ENABLED` | Show the username/password login form in the admin (default `False`; enable for local development). |

## Email

Standard Django email settings are available as `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`/`EMAIL_USE_SSL`, `EMAIL_BACKEND`, plus `CATCH_ALL_EMAIL` to redirect all outgoing mail to one address in non-production environments.
