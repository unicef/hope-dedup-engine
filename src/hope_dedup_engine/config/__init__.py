from environ import Env

DJANGO_HELP_BASE = "https://docs.djangoproject.com/en/5.0/ref/settings"


def setting(anchor):
    return f"@see {DJANGO_HELP_BASE}#{anchor}"


MANDATORY = {
    "DATABASE_URL": (str, "", "Database connection url"),
    "SECRET_KEY": (str, ""),
    "CACHE_URL": (str, "redis://localhost:6379/0"),
    "CELERY_BROKER_URL": (str, "redis://localhost:6379/0"),
}

DEVELOPMENT = {
    "DEBUG": (bool, True),
    "AUTHENTICATION_BACKENDS": (list, []),
    "SECURE_SSL_REDIRECT": (bool, False),
    "SECURE_HSTS_PRELOAD": (bool, False),
    "CSRF_COOKIE_SECURE": (bool, False),
    "SESSION_COOKIE_SECURE": (bool, False),
}

OPTIONAL = {
    "ADMIN_EMAIL": (str, "", "Admin email"),
    "ADMIN_PASSWORD": (str, "", "Admin password"),
    "ALLOWED_HOSTS": (list, ["127.0.0.1", "localhost"], "Django ALLOWED_HOSTS"),
    "AZURE_ACCOUNT_KEY": (str, "", "Azure account Key"),
    "AZURE_ACCOUNT_NAME": (str, ""),
    "AZURE_CONTAINER": (str, ""),
    "CELERY_VISIBILITY_TIMEOUT": (int, 1800),
    "CELERY_TASK_ALWAYS_EAGER": (bool, False),
    "CELERY_TASK_EAGER_PROPAGATES": (bool, True),
    "CSRF_COOKIE_SECURE": (bool, True),
    "DEBUG": (bool, False, "Django DEBUG"),
    "DEFAULT_FILE_STORAGE": (
        str,
        "hope_dedup_engine.apps.core.storage.MediaStorage",
        setting("storages"),
    ),
    "EMAIL_HOST_PASSWORD": (str, ""),
    "EMAIL_HOST_USER": (str, ""),
    "HOPE_FILE_STORAGE": (
        str,
        "hope_dedup_engine.apps.core.storage.HopeStorage",
        setting("storages"),
    ),
    "MEDIA_FILE_STORAGE": (
        str,
        "hope_dedup_engine.apps.core.storage.MediaStorage",
        setting("storages"),
    ),
    "SECURE_HSTS_SECONDS": (int, 60),
    "SESSION_COOKIE_HTTPONLY": (bool, True),
    "SECURE_SSL_REDIRECT": (bool, True),
    "SECURE_HSTS_PRELOAD": (bool, True),
    "SIGNING_BACKEND": (str, "django.core.signing.TimestampSigner"),
    "STATIC_FILE_STORAGE": (
        str,
        "hope_dedup_engine.apps.core.storage.StaticStorage",
        setting("storages"),
    ),
    "MEDIA_URL": (str, "/media/"),
    "MEDIA_ROOT": (str, "/tmp/media/"),
    "SENTRY_DSN": (str, ""),
    "SENTRY_URL": (str, "https://excubo.unicef.org/"),
    "SESSION_COOKIE_DOMAIN": (str, "unicef.org"),
    "SESSION_COOKIE_NAME": (str, "hpg_session"),
    "SESSION_COOKIE_PATH": (str, "/"),
    "SESSION_COOKIE_SECURE": (bool, True),
    "STATIC_URL": (str, "/static/"),
    "STATIC_ROOT": (str, "/tmp/static/"),
    "TIME_ZONE": (str, "UTC"),
    "WP_APPLICATION_SERVER_KEY": (str, ""),
    "WP_CLAIMS": (str, '{"sub": "mailto: hope@unicef.org","aud": "https://android.googleapis.com"}'),
    "WP_PRIVATE_KEY": (str, ""),
}


class SmartEnv(Env):
    def __init__(self, **scheme):  # type: ignore[no-untyped-def]
        self.raw = scheme
        super().__init__(**{k: v[:2] for k, v in scheme.items()})


env = SmartEnv(**{**DEVELOPMENT, **MANDATORY, **OPTIONAL})  # type: ignore[no-untyped-call]
