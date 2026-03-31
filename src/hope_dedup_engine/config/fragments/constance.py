from hope_dedup_engine.apps.api.const import (
    DETECTOR_BACKEND_CHOICES,
    DISTANCE_METRIC_CHOICES,
    RECOGNITION_MODEL_CHOICES,
)
from hope_dedup_engine.apps.security.constants import DEFAULT_GROUP_NAME
from .. import env

HOPE_API_TOKEN = env("HOPE_API_TOKEN")

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

CONSTANCE_CONFIG = {
    "DEFAULT_RECOGNITION_MODEL": (
        "Facenet512",
        "Specifies the face recognition model to be used for encoding face landmarks.",
        "recognition_model",
    ),
    "DEFAULT_DETECTOR_BACKEND": (
        "retinaface",
        "Specifies the face detector backend to be used for detecting faces in images.",
        "detector_backend",
    ),
    "DEFAULT_DISTANCE_METRIC": (
        "cosine",
        "Metric for measuring similarity.",
        "distance_metric",
    ),
    "DEFAULT_FACE_DETECTION_CONFIDENCE_THRESHOLD": (
        0.90,
        "Minimum confidence score (0..1) required for a detected face to be accepted. "
        "The effective range and typical values depend on the selected DETECTOR_BACKEND. "
        "Higher values keep only strong, well-localised faces; lower values also allow more uncertain "
        "or partially visible faces to pass.",
        "bounded_confidence_0_1",
    ),
    "DEFAULT_DUPLICATE_CONFIDENCE_THRESHOLD": (
        0.5,
        "Threshold on the face match confidence score (0..1). "
        "Only pairs with confidence at or above this value are treated as duplicates. "
        "Raising the threshold makes matching stricter (fewer false duplicates but more missed ones); "
        "lowering it makes matching more permissive (more potential duplicates and more false matches).",
        "bounded_confidence_0_1",
    ),
    "DEFAULT_SHARPNESS_THRESHOLD": (
        0.0,
        "Minimum sharpness score (0-1). Images below this threshold are rejected. 0 = disabled.",
        "bounded_confidence_0_1",
    ),
    "DEFAULT_DYNAMIC_RANGE_THRESHOLD": (
        0.0,
        "Minimum dynamic range score (0-1). Images below this threshold are rejected. 0 = disabled.",
        "bounded_confidence_0_1",
    ),
    "DEFAULT_NO_HEAD_COVER_THRESHOLD": (
        0.0,
        "Minimum no-head-cover score (0-1). Images below this threshold are rejected. 0 = disabled.",
        "bounded_confidence_0_1",
    ),
    "DEFAULT_EYES_OPEN_THRESHOLD": (
        0.0,
        "Minimum eyes-open score (0-1). Images below this threshold are rejected. 0 = disabled.",
        "bounded_confidence_0_1",
    ),
    "DEFAULT_INTER_EYE_DISTANCE_THRESHOLD": (
        0.0,
        "Minimum inter-eye distance score (0-1). Images below this threshold are rejected. 0 = disabled.",
        "bounded_confidence_0_1",
    ),
    "DEFAULT_UNIFIED_QUALITY_SCORE_THRESHOLD": (
        0.0,
        "Minimum unified quality score (0-1). Images below this threshold are rejected. 0 = disabled.",
        "bounded_confidence_0_1",
    ),
    "NEW_USER_IS_STAFF": (False, "Set any new user as staff", bool),
    "NEW_USER_DEFAULT_GROUP": (
        DEFAULT_GROUP_NAME,
        "Group to assign to any new user",
        str,
    ),
    "MAX_REFERENCE_PKS_ALLOWED_FOR_FINDINGS": (
        1000,
        "Set count of allowed reference pks as query params",
        int,
    ),
    "HOPE_API_TOKEN": (HOPE_API_TOKEN, "HOPE API Access Token", "write_only_text_input"),
}


CONSTANCE_CONFIG_FIELDSETS = {
    "Face detection and recognition settings": {
        "fields": (
            "DEFAULT_RECOGNITION_MODEL",
            "DEFAULT_DETECTOR_BACKEND",
            "DEFAULT_DISTANCE_METRIC",
            "DEFAULT_FACE_DETECTION_CONFIDENCE_THRESHOLD",
            "DEFAULT_DUPLICATE_CONFIDENCE_THRESHOLD",
            "DEFAULT_SHARPNESS_THRESHOLD",
            "DEFAULT_DYNAMIC_RANGE_THRESHOLD",
            "DEFAULT_NO_HEAD_COVER_THRESHOLD",
            "DEFAULT_EYES_OPEN_THRESHOLD",
            "DEFAULT_INTER_EYE_DISTANCE_THRESHOLD",
            "DEFAULT_UNIFIED_QUALITY_SCORE_THRESHOLD",
        ),
        "collapse": False,
    },
    "User settings": {
        "fields": ("NEW_USER_IS_STAFF", "NEW_USER_DEFAULT_GROUP"),
        "collapse": False,
    },
    "API settings": {
        "fields": (
            "MAX_REFERENCE_PKS_ALLOWED_FOR_FINDINGS",
            "HOPE_API_TOKEN",
        ),
        "collapse": False,
    },
}

CONSTANCE_ADDITIONAL_FIELDS = {
    "email": [
        "django.forms.EmailField",
        {},
    ],
    "bounded_confidence_0_1": [
        "django.forms.FloatField",
        {
            "min_value": 0.0,
            "max_value": 1.0,
        },
    ],
    "recognition_model": [
        "django.forms.ChoiceField",
        {"choices": RECOGNITION_MODEL_CHOICES},
    ],
    "detector_backend": [
        "django.forms.ChoiceField",
        {"choices": DETECTOR_BACKEND_CHOICES},
    ],
    "distance_metric": [
        "django.forms.ChoiceField",
        {"choices": DISTANCE_METRIC_CHOICES},
    ],
    "write_only_text_input": [
        "django.forms.fields.CharField",
        {
            "required": False,
            "widget": "hope_dedup_engine.utils.constance.WriteOnlyTextInput",
        },
    ],
}

CONSTANCE_DEFAULTS_MASK = "***"
CONSTANCE_MASKED_DEFAULTS = ("HOPE_API_TOKEN",)
