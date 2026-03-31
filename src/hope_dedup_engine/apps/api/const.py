RECOGNITION_MODEL_CHOICES = (
    ("Facenet512", "FaceNet 512D"),
    ("Facenet", "FaceNet 128D"),
    ("VGG-Face", "VGG-Face"),
    ("ArcFace", "ArcFace"),
    # DeepFace model is commented out due to compatibility issues with TensorFlow
    # versions. Requires LocallyConnected2D but it is no longer supported after tf 2.12.
    ("OpenFace", "OpenFace"),
    ("DeepID", "DeepID"),
    ("Dlib", "Dlib"),
    ("SFace", "SFace"),
    ("GhostFaceNet", "GhostFaceNet"),
)

DETECTOR_BACKEND_CHOICES = (
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
)

DISTANCE_METRIC_CHOICES = (
    ("cosine", "Cosine"),
    ("euclidean", "Euclidean"),
    ("euclidean_l2", "Euclidean L2"),
    ("angular", "Angular"),
)

DEDUPLICATION_SET = "deduplication_set"
DEDUPLICATION_SET_LIST = f"{DEDUPLICATION_SET}s"

PK = "pk"
GROUP = "group"
REFERENCE = "reference"
GROUP_REFERENCE_PK = f"{GROUP}__{REFERENCE}_{PK}"
DEDUPLICATION_SET_GROUP_PARAM = f"{DEDUPLICATION_SET}_{GROUP_REFERENCE_PK}"
DEDUPLICATION_SET_GROUP_FILTER = f"{DEDUPLICATION_SET}__{GROUP_REFERENCE_PK}"

ENCODING = "image"
ENCODING_LIST = f"{ENCODING}s"

BULK = "bulk"
BULK_ENCODING = f"{ENCODING}_{BULK}"
BULK_ENCODING_LIST = f"{ENCODING_LIST}_{BULK}"

DUPLICATE = "duplicate"
DUPLICATE_LIST = f"{DUPLICATE}s"
