from pathlib import Path
from typing import Final

from ..settings import env

DEEPFACE_HOME: Final[Path] = Path(env("DEEPFACE_HOME"))

DEEPFACE_WEIGHTS_BASE_LOCATION: Final[Path] = DEEPFACE_HOME / ".deepface/weights"

DEEPFACE_WEIGHTS: Final[dict[str, dict[str, str]]] = {
    "vgg_face_weights.h5": "https://github.com/serengil/deepface_models/releases/download/v1.0/vgg_face_weights.h5",
    "openface_weights.h5": "https://github.com/serengil/deepface_models/releases/download/v1.0/openface_weights.h5",
    "facenet_weights.h5": "https://github.com/serengil/deepface_models/releases/download/v1.0/facenet_weights.h5",
    "facenet512_weights.h5": "https://github.com/serengil/deepface_models/releases/download/v1.0/facenet512_weights.h5",
    "arcface_weights.h5": "https://github.com/serengil/deepface_models/releases/download/v1.0/arcface_weights.h5",
    "deepid_keras_weights.h5": "https://github.com/serengil/deepface_models/releases/download/v1.0/deepid_keras_weights.h5",
    "retinaface.h5": "https://github.com/serengil/deepface_models/releases/download/v1.0/retinaface.h5",
}
