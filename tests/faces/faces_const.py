from typing import Dict, Final

FILENAME: Final[str] = "test_file.jpg"
FILENAMES: Final[list[str]] = ["test_file.jpg", "test_file2.jpg"]
DEPLOY_PROTO_CONTENT: Final[str] = "input_shape { dim: 1 dim: 3 dim: 300 dim: 300 }"
DEPLOY_PROTO_SHAPE: Final[dict[str, int]] = {"batch_size": 1, "channels": 3, "height": 300, "width": 300}
FACE_REGIONS_INVALID: Final[list[list[tuple[int, int, int, int]]]] = [[], [(0, 0, 10)]]
FACE_REGIONS_VALID: Final[list[tuple[int, int, int, int]]] = [
    (10, 10, 20, 20),
    (30, 30, 40, 40),
]
FACE_DETECTION_CONFIDENCE: Final[float] = 0.7
FACE_DETECTIONS: Final[list[tuple[float]]] = [
    (0, 0, 0.95, 0.1, 0.1, 0.2, 0.2),  # with confidence 0.95 -> valid detection
    (0, 0, 0.75, 0.3, 0.3, 0.4, 0.4),  # with confidence 0.75 -> valid detection
    (0, 0, 0.15, 0.1, 0.1, 0.2, 0.2),  # with confidence 0.15 -> invalid detection
]
IMAGE_SIZE: Final[tuple[int, int, int]] = (100, 100, 3)  # Size of the image after decoding (h, w, number of channels)
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
