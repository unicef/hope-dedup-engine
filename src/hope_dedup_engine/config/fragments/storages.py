from hope_dedup_engine.config import env

STORAGES = {
    "default": {
        "BACKEND": env.str("DEFAULT_FILE_STORAGE", default="hope_dedup_engine.apps.core.storage.MediaStorage"),
    },
    "staticfiles": {
        "BACKEND": env.str("STATIC_FILE_STORAGE", default="django.contrib.staticfiles.storage.StaticFilesStorage"),
    },
}
