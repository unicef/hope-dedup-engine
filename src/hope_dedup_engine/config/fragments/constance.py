from hope_dedup_engine.apps.security.constants import DEFAULT_GROUP_NAME

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
}


CONSTANCE_CONFIG_FIELDSETS = {
    "Face detection and recognition settings": {
        "fields": (
            "DEFAULT_RECOGNITION_MODEL",
            "DEFAULT_DETECTOR_BACKEND",
            "DEFAULT_DISTANCE_METRIC",
            "DEFAULT_FACE_DETECTION_CONFIDENCE_THRESHOLD",
            "DEFAULT_DUPLICATE_CONFIDENCE_THRESHOLD",
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
    "bounded_confidence_0_1": [
        "django.forms.FloatField",
        {
            "min_value": 0.0,
            "max_value": 1.0,
        },
    ],
    "recognition_model": [
        "django.forms.ChoiceField",
        {
            "choices": (
                ("Facenet512", "FaceNet 512D"),
                ("Facenet", "FaceNet 128D"),
                ("VGG-Face", "VGG-Face"),
                ("ArcFace", "ArcFace"),
                ("DeepFace", "DeepFace"),
                ("OpenFace", "OpenFace"),
                ("DeepID", "DeepID"),
                ("Dlib", "Dlib"),
                ("SFace", "SFace"),
                ("GhostFaceNet", "GhostFaceNet"),
            ),
        },
    ],
    "detector_backend": [
        "django.forms.ChoiceField",
        {
            "choices": (
                ("retinaface", "RetinaFace"),
                ("mtcnn", "MTCNN"),
                ("ssd", "SSD"),
                ("dlib", "Dlib"),
                ("mediapipe", "MediaPipe"),
                ("opencv", "OpenCV"),
                ("yolov8n", "YOLOv8n"),
                ("yolov8m", "YOLOv8m"),
                ("yolov8l", "YOLOv8l"),
                ("yolov11n", "YOLOv11n"),
                ("yolov11s", "YOLOv11s"),
                ("yolov11m", "YOLOv11m"),
                ("yolov11l", "YOLOv11l"),
                ("yolov12n", "YOLOv12n"),
                ("yolov12s", "YOLOv12s"),
                ("yolov12m", "YOLOv12m"),
                ("yolov12l", "YOLOv12l"),
                ("centerface", "CenterFace"),
            ),
        },
    ],
    "distance_metric": [
        "django.forms.ChoiceField",
        {
            "choices": (
                ("cosine", "Cosine"),
                ("euclidean", "Euclidean"),
                ("euclidean_l2", "Euclidean L2"),
                ("angular", "Angular"),
            ),
        },
    ],
}
