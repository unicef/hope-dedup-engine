import os
from pathlib import Path
from . import env

SETTINGS_DIR = Path(__file__).parent
PACKAGE_DIR = SETTINGS_DIR.parent
DEVELOPMENT_DIR = PACKAGE_DIR.parent.parent

DEBUG = env.bool("DEBUG")

SECRET_KEY = env("SECRET_KEY")

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

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
SITE_ID = 1
INTERNAL_IPS = ["127.0.0.1", "localhost"]

ROOT_URLCONF = "hope_dedup_engine.config.urls"
WSGI_APPLICATION = "hope_dedup_engine.config.wsgi.application"

AUTH_USER_MODEL = "core.User"

HOST = env("HOST", default="http://localhost:8000")

# django-cors-headers: https://github.com/ottoyiu/django-cors-headers
CORS_ORIGIN_ALLOW_ALL = env("CORS_ORIGIN_ALLOW_ALL", default=False)

USER_FIELDS = ["username", "email", "first_name", "last_name"]
USERNAME_IS_FULL_EMAIL = True

POWER_QUERY_DB_ALIAS = "read_only"
POWER_QUERY_EXTRA_CONNECTIONS = []

from hope_dedup_engine.config.fragments.middleware import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.installed_apps import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.databases import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.celery import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.constance import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.debug_toolbar import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.drf import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.drf_spectacular import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.email import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.i18n import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.jwt import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.loggers import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.redis import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.sentry import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.smart_admin import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.social_auth import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.storages import *  # noqa: F403, F401, E402
from hope_dedup_engine.config.fragments.templates import *  # noqa: F403, F401, E402
