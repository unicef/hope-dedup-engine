import datetime
import os
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from . import env

SETTINGS_DIR = Path(__file__).parent
PACKAGE_DIR = SETTINGS_DIR.parent
DEVELOPMENT_DIR = PACKAGE_DIR.parent.parent

DEBUG = env.bool("DEBUG")

RO_CONN = dict(**env.db("DATABASE_HOPE_URL")).copy()
RO_CONN.update(
    **{
        "OPTIONS": {"options": "-c default_transaction_read_only=on"},
    }
)
RO_CONN.update(
    {
        "OPTIONS": {"options": "-c default_transaction_read_only=on"},
        "TEST": {
            "READ_ONLY": True,  # Do not manage this database during tests
        },
    }
)
DATABASES = {
    "default": env.db("DATABASE_URL"),
    "hope_ro": RO_CONN,
}
DATABASE_ROUTERS = ("hope_dedup_engine.apps.core.dbrouters.DbRouter",)
DATABASE_APPS_MAPPING: dict[str, str] = {
    "hope": "hope",
}

PROJECT_APPS = [
    "hope_dedup_engine.web",
    "hope_dedup_engine.apps.core.apps.AppConfig",
    "unicef_security",
]
DJANGO_APPS = [
    "django.contrib.contenttypes",
    "advanced_filters",
    "django.contrib.auth",
    "django.contrib.humanize",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django.contrib.admin",
    "django_extensions",
    "django_filters",
]
OTHER_APPS = [
    "corsheaders",
    "django_fsm",
    "social_django",
    "admin_extra_buttons",
    "adminactions",
    "adminfilters",
    "adminfilters.depot",
    "smart_admin.apps.SmartTemplateConfig",
    "import_export",
    "constance",
    "rest_framework",
    "django_celery_beat",
    "django_celery_results",
    # "power_query",
]
INSTALLED_APPS = DJANGO_APPS + OTHER_APPS + PROJECT_APPS

MIDDLEWARE = (
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "unicef_security.middleware.UNICEFSocialAuthExceptionMiddleware",
)

AUTHENTICATION_BACKENDS = (
    "social_core.backends.azuread_tenant.AzureADTenantOAuth2",
    "django.contrib.auth.backends.ModelBackend",
    *env("AUTHENTICATION_BACKENDS"),
)

# path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
MEDIA_ROOT = env("MEDIA_ROOT")
MEDIA_URL = env("MEDIA_URL")
STATIC_ROOT = env("STATIC_ROOT", default=os.path.join(BASE_DIR, "static"))
STATIC_URL = env("STATIC_URL", default="/static/")
STATICFILES_DIRS = []
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STORAGES = {
    "default": {
        "BACKEND": env.str("DEFAULT_FILE_STORAGE", default="hope_dedup_engine.apps.core.storage.MediaStorage"),
    },
    "staticfiles": {
        "BACKEND": env.str("STATIC_FILE_STORAGE", default="django.contrib.staticfiles.storage.StaticFilesStorage"),
    },
}

SECRET_KEY = env("SECRET_KEY")

ALLOWED_HOSTS = (
    # env("ALLOWED_HOST", default="localhost"),
    # "0.0.0.0",
    # TODO
    "*",
)

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_URL = "/accounts/logout"
LOGOUT_REDIRECT_URL = "/"

# TIME_ZONE = env('TIME_ZONE', default='UTC')
# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"
ugettext = lambda s: s  # noqa
LANGUAGES = (
    ("es", ugettext("Spanish")),
    ("fr", ugettext("French")),
    ("en", ugettext("English")),
    ("ar", ugettext("Arabic")),
)
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
SITE_ID = 1
INTERNAL_IPS = ["127.0.0.1", "localhost"]

CACHE_URL = env("CACHE_URL")
REDIS_URL = urlparse(CACHE_URL).hostname
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": CACHE_URL,
    }
}

ROOT_URLCONF = "hope_dedup_engine.config.urls"
WSGI_APPLICATION = "hope_dedup_engine.config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(PACKAGE_DIR / "templates")],
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "constance.context_processors.config",
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
            ],
            "libraries": {
                "staticfiles": "django.templatetags.static",
                "i18n": "django.templatetags.i18n",
            },
        },
    },
]

LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler", "level": "INFO"},
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

AUTH_USER_MODEL = "core.User"

HOST = env("HOST", default="http://localhost:8000")

# django-cors-headers: https://github.com/ottoyiu/django-cors-headers
CORS_ORIGIN_ALLOW_ALL = env("CORS_ORIGIN_ALLOW_ALL", default=False)

JWT_AUTH = {
    "JWT_VERIFY": False,  # this requires private key
    "JWT_VERIFY_EXPIRATION": True,
    "JWT_LEEWAY": 60,
    "JWT_EXPIRATION_DELTA": datetime.timedelta(seconds=30000),
    "JWT_AUDIENCE": None,
    "JWT_ISSUER": None,
    "JWT_ALLOW_REFRESH": False,
    "JWT_REFRESH_EXPIRATION_DELTA": datetime.timedelta(days=7),
    "JWT_AUTH_HEADER_PREFIX": "JWT",
    "JWT_SECRET_KEY": SECRET_KEY,
    "JWT_DECODE_HANDLER": "rest_framework_jwt.utils.jwt_decode_handler",
    # Keys will be set in core.apps.Config.ready()
    "JWT_PUBLIC_KEY": "?",
    # 'JWT_PRIVATE_KEY': wallet.get_private(),
    # 'JWT_PRIVATE_KEY': None,
    "JWT_ALGORITHM": "RS256",
}

DEFAULT_FROM_EMAIL = "hope@unicef.org"
# EMAIL_BACKEND = "djcelery_email.backends.CeleryEmailBackend" # TODO: when ready, add djcelery_email
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_PORT = env("EMAIL_PORT", default=25)
EMAIL_USE_TLS = env("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env("EMAIL_USE_SSL", default=False)

USER_FIELDS = ["username", "email", "first_name", "last_name"]
USERNAME_IS_FULL_EMAIL = True

from hope_dedup_engine.config.fragments.customs import *  # noqa: F403, F401, E402
