from typing import Final

from hope_dedup_engine.config import env

AZURE_CONTAINER_HDE: Final[str] = "hde"
AZURE_CONTAINER_HOPE: Final[str] = "hope"
AZURE_CONTAINER_DNN: Final[str] = "dnn"

CV2DNN_DIR: Final[str] = env("CV2DNN_DIR")
DNN_FILES: Final[dict[str, dict[str, str]]] = {
    "prototxt": {
        "filename": "deploy.prototxt",
        "sources": {
            "github": "https://raw.githubusercontent.com/sr6033/face-detection-with-OpenCV-and-DNN/master/deploy.prototxt.txt",  # noqa: E501
            "azure": "deploy.prototxt",
        },
        "local_path": f"{CV2DNN_DIR}/deploy.prototxt",
    },
    "caffemodel": {
        "filename": "res10_300x300_ssd_iter_140000.caffemodel",
        "sources": {
            "github": "https://raw.githubusercontent.com/sr6033/face-detection-with-OpenCV-and-DNN/master/res10_300x300_ssd_iter_140000.caffemodel",  # noqa: E501
            "azure": "res10_300x300_ssd_iter_140000.caffemodel",
        },
        "local_path": f"{CV2DNN_DIR}/res10_300x300_ssd_iter_140000.caffemodel",
    },
}
