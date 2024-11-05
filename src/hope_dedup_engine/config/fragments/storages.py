from typing import Final

DNN_FILES: Final[dict[str, dict[str, str]]] = {
    "prototxt": {
        "filename": "deploy.prototxt.txt",
        "sources": {
            "github": "https://raw.githubusercontent.com/sr6033/face-detection-with-OpenCV-and-DNN/master/deploy.prototxt.txt",  # noqa: E501
            "azure": "deploy.prototxt.txt",
        },
    },
    "caffemodel": {
        "filename": "res10_300x300_ssd_iter_140000.caffemodel",
        "sources": {
            "github": "https://raw.githubusercontent.com/sr6033/face-detection-with-OpenCV-and-DNN/master/res10_300x300_ssd_iter_140000.caffemodel",  # noqa: E501
            "azure": "res10_300x300_ssd_iter_140000.caffemodel",
        },
    },
}
