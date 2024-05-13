from hope_dedup_engine.apps.security.constants import DEFAULT_GROUP_NAME

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

CONSTANCE_ADDITIONAL_FIELDS = {
    "email": [
        "django.forms.EmailField",
        {},
    ],
}

CONSTANCE_CONFIG = {
    "NEW_USER_IS_STAFF": (False, "Set any new user as staff", bool),
    "NEW_USER_DEFAULT_GROUP": (DEFAULT_GROUP_NAME, "Group to assign to any new user", str),
}
