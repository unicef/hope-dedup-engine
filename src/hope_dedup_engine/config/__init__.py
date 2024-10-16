from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Tuple, TypeAlias, Union

from smart_env import SmartEnv

if TYPE_CHECKING:
    ConfigItem: TypeAlias = Union[
        Tuple[type, Any, str, Any], Tuple[type, Any, str], Tuple[type, Any]
    ]

DJANGO_HELP_BASE = "https://docs.djangoproject.com/en/5.1/ref/settings"


def setting(anchor: str) -> str:
    return f"@see {DJANGO_HELP_BASE}#{anchor}"


def celery_doc(anchor: str) -> str:
    return (
        f"@see https://docs.celeryq.dev/en/stable/"
        f"userguide/configuration.html#{anchor}"
    )


class Group(Enum):
    DJANGO = 1


CONFIG: "Dict[str, ConfigItem]" = {
    "ADMIN_EMAIL": (
        str,
        "",
        "admin",
        False,
        "Initial user created at first deploy",
    ),
    "ADMIN_PASSWORD": (
        str,
        "",
        "",
        False,
        "Password for initial user created at first deploy",
    ),
    "ALLOWED_HOSTS": (
        list,
        [],
        ["127.0.0.1", "localhost"],
        True,
        setting("allowed-hosts"),
    ),
    "AUTHENTICATION_BACKENDS": (
        list,
        [],
        [],
        False,
        setting("authentication-backends"),
    ),
    "AZURE_CLIENT_SECRET": (str, ""),
    "AZURE_TENANT_ID": (str, ""),
    "AZURE_CLIENT_KEY": (str, ""),
    "CACHE_URL": (
        str,
        SmartEnv.NOTSET,
        "redis://localhost:6379/0",
        True,
        setting("cache-url"),
    ),
    "CATCH_ALL_EMAIL": (
        str,
        "",
        "",
        False,
        "If set all the emails will be sent to this address",
    ),
    "CELERY_BROKER_URL": (
        str,
        "",
        "",
        True,
        "https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html",
    ),
    "CELERY_TASK_ALWAYS_EAGER": (
        bool,
        False,
        True,
        False,
        f"{celery_doc}#std-setting-task_always_eager",
    ),
    "CELERY_TASK_EAGER_PROPAGATES": (
        bool,
        True,
        True,
        False,
        f"{celery_doc}#task-eager-propagates",
    ),
    "CELERY_VISIBILITY_TIMEOUT": (
        int,
        1800,
        1800,
        False,
        f"{celery_doc}#broker-transport-options",
    ),
    "CSRF_COOKIE_SECURE": (bool, True, False, False, setting("csrf-cookie-secure")),
    "DATABASE_URL": (
        str,
        SmartEnv.NOTSET,
        SmartEnv.NOTSET,
        True,
        "https://django-environ.readthedocs.io/en/latest/types.html#environ-env-db-url",
    ),
    "DEBUG": (bool, False, True, False, setting("debug")),
    "DEFAULT_ROOT": (
        str,
        "/var/default/",
        "/tmp/default",  # nosec
        True,
        "Default root for stored locally files",
    ),
    "DEMO_IMAGES_PATH": (str, "demo_images"),
    "DNN_FILES_PATH": (str, "dnn_files"),
    # "EMAIL_BACKEND": (
    #     str,
    #     "django.core.mail.backends.smtp.EmailBackend",
    #     setting("email-backend"),
    #     True,
    # ),
    "EMAIL_HOST": (str, "", "", False, setting("email-host")),
    "EMAIL_HOST_USER": (str, "", "", False, setting("email-host-user")),
    "EMAIL_HOST_PASSWORD": (str, "", "", False, setting("email-host-password")),
    "EMAIL_PORT": (int, "25", "25", False, setting("email-port")),
    "EMAIL_SUBJECT_PREFIX": (
        str,
        "[Hope-dedupe]",
        "[Hope-dedupe-dev]",
        False,
        setting("email-subject-prefix"),
    ),
    "EMAIL_USE_LOCALTIME": (bool, False, False, False, setting("email-use-localtime")),
    "EMAIL_USE_TLS": (bool, False, False, False, setting("email-use-tls")),
    "EMAIL_USE_SSL": (bool, False, False, False, setting("email-use-ssl")),
    "EMAIL_TIMEOUT": (str, None, None, False, setting("email-timeout")),
    "FILE_STORAGE_DEFAULT": (
        str,
        "django.core.files.storage.FileSystemStorage",
        setting("storages"),
    ),
    "FILE_STORAGE_MEDIA": (
        str,
        "django.core.files.storage.FileSystemStorage",
        setting("storages"),
    ),
    "FILE_STORAGE_STATIC": (
        str,
        "django.contrib.staticfiles.storage.StaticFilesStorage",
        setting("storages"),
    ),
    "FILE_STORAGE_HOPE": (
        str,
        "storages.backends.azure_storage.AzureStorage",
        setting("storages"),
    ),
    "FILE_STORAGE_DNN": (
        str,
        "storages.backends.azure_storage.AzureStorage",
        setting("storages"),
    ),
    "LOG_LEVEL": (str, "CRITICAL", "DEBUG", False, setting("logging-level")),
    "MEDIA_ROOT": (
        str,
        "/var/media/",
        "/tmp/media",  # nosec
        True,
        setting("media-root"),
    ),
    "MEDIA_URL": (str, "/media/", "/media", False, setting("media-root")),  # nosec
    "ROOT_TOKEN_HEADER": (str, "x-root-token", "x-root-token"),
    "ROOT_TOKEN": (str, ""),
    "SECRET_KEY": (
        str,
        "",
        "super_sensitive_key_just_for_testing",
        True,
        setting("secret-key"),
    ),
    "SECURE_HSTS_PRELOAD": (bool, True, False, False, setting("secure-hsts-preload")),
    "SECURE_HSTS_SECONDS": (int, 60, 0, False, setting("secure-hsts-seconds")),
    "SECURE_SSL_REDIRECT": (bool, True, False, False, setting("secure-ssl-redirect")),
    "SENTRY_DSN": (str, "", "", False, "Sentry DSN"),
    "SENTRY_ENVIRONMENT": (str, "production", "develop", False, "Sentry Environment"),
    "SENTRY_URL": (str, "", "", False, "Sentry server url"),
    "SESSION_COOKIE_DOMAIN": (
        str,
        SmartEnv.NOTSET,
        "localhost",
        False,
        setting("std-setting-SESSION_COOKIE_DOMAIN"),
    ),
    "SESSION_COOKIE_HTTPONLY": (
        bool,
        True,
        False,
        False,
        setting("session-cookie-httponly"),
    ),
    "SESSION_COOKIE_NAME": (str, "dedupe_session", setting("session-cookie-name")),
    "SESSION_COOKIE_PATH": (str, "/", setting("session-cookie-path")),
    "SESSION_COOKIE_SECURE": (
        bool,
        True,
        False,
        False,
        setting("session-cookie-secure"),
    ),
    "SIGNING_BACKEND": (
        str,
        "django.core.signing.TimestampSigner",
        setting("signing-backend"),
    ),
    "SOCIAL_AUTH_LOGIN_URL": (str, "/login/", "", False, ""),
    "SOCIAL_AUTH_RAISE_EXCEPTIONS": (bool, False, True, False),
    "SOCIAL_AUTH_REDIRECT_IS_HTTPS": (bool, True, False, False, ""),
    "STATIC_ROOT": (
        str,
        "/var/static",
        "/tmp/static",
        True,
        setting("static-root"),
    ),  # nosec
    "STATIC_URL": (str, "/static/", "/static/", False, setting("static-url")),  # nosec
    "TIME_ZONE": (str, "UTC", "UTC", False, setting("std-setting-TIME_ZONE")),
}


env = SmartEnv(**CONFIG)  # type: ignore[no-untyped-call]
