from hope_dedup_engine.config import env

AZURE_ACCOUNT_NAME = env("AZURE_ACCOUNT_NAME")
AZURE_ACCOUNT_KEY = env("AZURE_ACCOUNT_KEY")
AZURE_CUSTOM_DOMAIN = env("AZURE_CUSTOM_DOMAIN")
AZURE_CONNECTION_STRING = env("AZURE_CONNECTION_STRING")

AZURE_CONTAINER_HDE = "hde"
AZURE_CONTAINER_HOPE = "hope"  # static-dde
AZURE_CONTAINER_DNN = "dnn"  # model-dde

CV2DNN_DIR = env("CV2DNN_DIR")
DNN_FILES = {
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
