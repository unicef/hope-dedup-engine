from hope_dedup_engine.apps.security.constants import DEFAULT_GROUP_NAME

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

CONSTANCE_CONFIG = {
    "MODEL_NAME": (
        "VGG-Face",
        "Specifies the face recognition model to be used for encoding face landmarks.",
        "face_recognition_models",
    ),
    "DETECTOR_BACKEND": (
        "retinaface",
        """
        Specifies the face detector backend used during the Face Detection and Alignment stages to locate faces
         and ensure consistent facial alignment in images.
        """,
        "face_detector_backend",
    ),
    "FACE_DISTANCE_THRESHOLD": (
        0.4,
        """
        Specifies the maximum allowable distance between two face embeddings for them to be considered a match.
        This similarity threshold is crucial for assessing whether two faces belong to the same individual,
        as it establishes the similarity limit. Lower values result in stricter matching, while higher values allow
        for more lenient matches.
        """,
        "float_range_0_1",
    ),
    "NEW_USER_IS_STAFF": (False, "Set any new user as staff", bool),
    "NEW_USER_DEFAULT_GROUP": (
        DEFAULT_GROUP_NAME,
        "Group to assign to any new user",
        str,
    ),
}


CONSTANCE_CONFIG_FIELDSETS = {
    "Face detection and recognition settings": {
        "fields": (
            "MODEL_NAME",
            "DETECTOR_BACKEND",
            "FACE_DISTANCE_THRESHOLD",
        ),
        "collapse": False,
    },
    "User settings": {
        "fields": ("NEW_USER_IS_STAFF", "NEW_USER_DEFAULT_GROUP"),
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
    "float_range_0_1": [
        "django.forms.FloatField",
        {
            "min_value": 0.0,
            "max_value": 1.0,
        },
    ],
}
