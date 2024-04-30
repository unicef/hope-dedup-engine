PROJECT_APPS = [
    "hope_dedup_engine.web",
    "hope_dedup_engine.apps.core.apps.AppConfig",
    "unicef_security",
]

DJANGO_APPS = [
    "advanced_filters",
    "django.contrib.contenttypes",
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
    "import_export",
    "constance",
    "rest_framework",
    "django_celery_beat",
    "django_celery_results",
    "power_query",
]

INSTALLED_APPS = DJANGO_APPS + OTHER_APPS + PROJECT_APPS
