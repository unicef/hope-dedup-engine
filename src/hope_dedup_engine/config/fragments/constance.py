import cv2

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
    "FACE_DETECTION_CONFIDENCE": (0.7, "Face detection confidence threshold", float),
    "DISTANCE_THRESHOLD": (0.5, "Face distance threshold", float),
    "DNN_BACKEND": (cv2.dnn.DNN_TARGET_CPU, "DNN backend", "dnn_backend"),
    "DNN_TARGET": (cv2.dnn.DNN_TARGET_CPU, "DNN target", "dnn_target"),
}

CONSTANCE_CONFIG_FIELDSETS = {
    "User settings": {
        "fields": ("NEW_USER_IS_STAFF", "NEW_USER_DEFAULT_GROUP"),
        "collapse": False,
    },
    "Face recognition settings": {
        "fields": ("FACE_DETECTION_CONFIDENCE", "DISTANCE_THRESHOLD", "DNN_BACKEND", "DNN_TARGET"),
        "collapse": False,
    },
}

CONSTANCE_ADDITIONAL_FIELDS = {
    "dnn_backend": [
        "django.forms.ChoiceField",
        {
            "choices": ((cv2.dnn.DNN_TARGET_CPU, "DNN_TARGET_CPU"),),
        },
    ],
    "dnn_target": [
        "django.forms.ChoiceField",
        {
            "choices": ((cv2.dnn.DNN_TARGET_CPU, "DNN_TARGET_CPU"),),
        },
    ],
}
