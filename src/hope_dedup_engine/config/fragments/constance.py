from hope_dedup_engine.apps.security.constants import DEFAULT_GROUP_NAME

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

CONSTANCE_CONFIG = {
    "FACE_RECOGNITION_MODEL": (
        "VGG-Face",
        "Specifies the face recognition model to be used for encoding face landmarks.",
        "face_recognition_models",
    ),
    "FACE_DETECTOR_BACKEND": (
        "retinaface",
        "Specifies the face detector backend to be used for detecting faces in images.",
        "face_detector_backend",
    ),
    "FACE_DISTANCE_THRESHOLD": (
        0.4,
        """
        Specifies the maximum allowable distance between two face embeddings for them to be considered a match.
        This tolerance threshold is crucial for assessing whether two faces belong to the same individual,
        as it establishes the similarity limit. Lower values result in stricter matching, while higher values allow
        for more lenient matches.
        """,
        float,
    ),
    "NEW_USER_IS_STAFF": (False, "Set any new user as staff", bool),
    "NEW_USER_DEFAULT_GROUP": (
        DEFAULT_GROUP_NAME,
        "Group to assign to any new user",
        str,
    ),
    "MAX_REFERENCE_PKS_ALLOWED_FOR_FINDINGS": (1000, "Set count of allowed reference pks as query params", int),
}


CONSTANCE_CONFIG_FIELDSETS = {
    "Face detection and recognition settings": {
        "fields": (
            "FACE_RECOGNITION_MODEL",
            "FACE_DETECTOR_BACKEND",
            "FACE_DISTANCE_THRESHOLD",
        ),
        "collapse": False,
    },
    "User settings": {
        "fields": ("NEW_USER_IS_STAFF", "NEW_USER_DEFAULT_GROUP"),
        "collapse": False,
    },
    "API settings": {
        "fields": ("MAX_REFERENCE_PKS_ALLOWED_FOR_FINDINGS",),
        "collapse": False,
    },
}

CONSTANCE_ADDITIONAL_FIELDS = {
    "email": [
        "django.forms.EmailField",
        {},
    ],
    "face_recognition_models": [
        "django.forms.ChoiceField",
        {
            "choices": (("VGG-Face", "VGG-Face"),),
        },
    ],
    "face_detector_backend": [
        "django.forms.ChoiceField",
        {
            "choices": (("retinaface", "RetinaFace"),),
        },
    ],
}
