from typing import Final

FILENAME: Final[str] = "test_file.jpg"
FILENAME_ENCODED: Final[str] = "test_file.jpg.npy"
FILENAME_ENCODED_FORMAT: Final[str] = "{}.npy"
FILENAMES: Final[list[str]] = ["test_file.jpg", "test_file2.jpg", "test_file3.jpg"]
IGNORE_PAIRS: Final[list[list[str, str]]] = [
    ["ignore_file.jpg", "ignore_file2.jpg"],
    ["ignore_file4.jpg", "ignore_file3.jpg"],
]

DNN_FILE = {
    "name": FILENAME,
    "content": [b"Hello, world!"],
    "timeout": 3 * 60,
    "chunks": 3,
    "url": "https://raw.githubusercontent.com/sr6033/face-detection-with-OpenCV-and-DNN/master/deploy.prototxt.txt",
}

DNN_FILES_TIMEOUT: Final[int] = (3 * 60,)
DNN_FILES_CHUNK_SIZE: Final[int] = (128 * 1024,)
DNN_FILES_BINARY_ITERABLE_FILE: Final[list[bytes]] = [b"Hello, world!"] * 3
DNN_GITHUB_URL: Final[str] = (
    "https://raw.githubusercontent.com/sr6033/face-detection-with-OpenCV-and-DNN/master/deploy.prototxt.txt"
)
DNN_FILENAME: Final[str] = "deploy.prototxt"


CELERY_TASK_NAME: Final[str] = "Deduplicate"
CELERY_TASK_TTL: Final[int] = 1 * 60 * 60
CELERY_TASK_DELAYS: Final[dict[str, int]] = {
    "SoftTimeLimitExceeded": 5 * 60 * 60,
    "TimeLimitExceeded": 10 * 60 * 60,
    "CustomException": 0,
}

DEPLOY_PROTO_CONTENT: Final[str] = "input_shape { dim: 1 dim: 3 dim: 300 dim: 300 }"
DEPLOY_PROTO_SHAPE: Final[dict[str, int]] = {
    "batch_size": 1,
    "channels": 3,
    "height": 300,
    "width": 300,
}
FACE_REGIONS_INVALID: Final[list[list[tuple[int, int, int, int]]]] = [[], [(0, 0, 10)]]
FACE_REGIONS_VALID: Final[list[tuple[int, int, int, int]]] = [
    (10, 10, 20, 20),
    (30, 30, 40, 40),
]
BLOB_FROM_IMAGE_SCALE_FACTOR: Final[float] = 1.0
BLOB_FROM_IMAGE_MEAN_VALUES: Final[tuple[float, float, float]] = (104.0, 177.0, 123.0)
FACE_DETECTION_CONFIDENCE: Final[float] = 0.5
FACE_DETECTIONS: Final[list[tuple[float]]] = [
    (0, 0, 0.95, 0.1, 0.1, 0.2, 0.2),  # with confidence 0.95 -> valid detection
    (0, 0, 0.75, 0.3, 0.3, 0.4, 0.4),  # with confidence 0.75 -> valid detection
    (0, 0, 0.15, 0.1, 0.1, 0.2, 0.2),  # with confidence 0.15 -> invalid detection
]
IMAGE_SIZE: Final[tuple[int, int, int]] = (
    100,
    100,
    3,
)  # Size of the image after decoding (h, w, number of channels)
RESIZED_IMAGE_SIZE: Final[tuple[int, int, int]] = (
    300,
    300,
    3,
)  # Size of the image after resizing for processing (h, w, number of channels)
BLOB_SHAPE: Final[tuple[int, int, int, int]] = (
    1,
    3,
    300,
    300,
)  # Shape of the blob (4D tensor) for input to the neural network (batch_size, channels, h, w)
