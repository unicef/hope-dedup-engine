from hope_dedup_engine.config import env
from hope_dedup_engine.config.settings import DEBUG, INSTALLED_APPS, MIDDLEWARE, CACHE_URL
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

CELERY_ACCEPT_CONTENT = ["pickle", "json", "application/text"]
CELERY_BROKER_URL = env("CACHE_URL")
CELERY_BROKER_VISIBILITY_VAR = env("CELERY_VISIBILITY_TIMEOUT", default=1800)  # in seconds
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": int(CELERY_BROKER_VISIBILITY_VAR)}
CELERY_RESULT_BACKEND = "django-db"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"
# Sensible settings for celery
CELERY_TASK_ALWAYS_EAGER = env("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_PUBLISH_RETRY = True
CELERY_WORKER_DISABLE_RATE_LIMITS = False
CELERY_TASK_IGNORE_RESULT = True
CELERY_SEND_TASK_ERROR_EMAILS = False
CELERY_RESULT_EXPIRES = 600
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
}

SENTRY_DSN = env("SENTRY_DSN", default=None)  # noqa: F405
if SENTRY_DSN:  # pragma: no cover
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        # by default this is False, must be set to True so the library attaches the request data to the event
        send_default_pii=True,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        environment=env("SENTRY_ENVIRONMENT", default=None),
    )

CONSTANCE_CONFIG = {}
CONSTANCE_REDIS_CONNECTION = CACHE_URL

SOCIAL_AUTH_SECRET = env.str("AZURE_CLIENT_SECRET", default="")
SOCIAL_AUTH_TENANT_ID = env("AZURE_TENANT_ID", default="")
SOCIAL_AUTH_KEY = env.str("AZURE_CLIENT_KEY", default="")
SOCIAL_AUTH_URL_NAMESPACE = "social"
SOCIAL_AUTH_SANITIZE_REDIRECTS = False
SOCIAL_AUTH_JSONFIELD_ENABLED = True
SOCIAL_AUTH_USER_MODEL = "core.User"
SOCIAL_AUTH_PIPELINE = (
    "unicef_security.pipeline.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.social_auth.associate_by_email",
    "unicef_security.pipeline.create_unicef_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
)

INSTALLED_APPS += ["power_query",]
POWER_QUERY_DB_ALIAS = "read_only"
POWER_QUERY_EXTRA_CONNECTIONS = []

if DEBUG:  # pragma: no cover
    INSTALLED_APPS += ("debug_toolbar",)  # noqa
    MIDDLEWARE += ("debug_toolbar.middleware.DebugToolbarMiddleware",)  # noqa
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TEMPLATE_CONTEXT": True,
    }

    INSTALLED_APPS += ("drf_spectacular", "drf_spectacular_sidecar")  # noqa        
    REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"
    SPECTACULAR_SETTINGS = {
        "TITLE": "Payment Gateway API",
        "DESCRIPTION": "Payment Gateway to integrate HOPE with FSP",
        "VERSION": "1.0.0",
        "SERVE_INCLUDE_SCHEMA": True,
        "SWAGGER_UI_DIST": "SIDECAR",
        "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
        "REDOC_DIST": "SIDECAR",
    }
