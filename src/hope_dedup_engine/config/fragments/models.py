from pathlib import Path
from typing import Final

from ..settings import env

DEEPFACE_HOME: Final[Path] = Path(env("DEEPFACE_HOME"))

DEEPFACE_WEIGHTS_BASE_LOCATION: Final[Path] = DEEPFACE_HOME / ".deepface/weights"


DEEPFACE_WEIGHTS: Final[dict[str, str]] = {
    "arcface_weights.pth": "https://github.com/serengil/deepface_models/releases/download/v1.0/arcface_weights.pth",
    "centerface.onnx": "https://github.com/Star-Clouds/CenterFace/raw/master/models/onnx/centerface.onnx",
    "deepid_weights.pth": "https://github.com/serengil/deepface_models/releases/download/v1.0/deepid_weights.pth",
    "deploy.prototxt": "https://github.com/opencv/opencv/raw/3.4.0/samples/dnn/face_detector/deploy.prototxt",
    "dlib_face_recognition_resnet_model_v1.dat.bz2": "http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2",
    "face_recognition_sface_2021dec.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    "facenet512_weights.pth": "https://github.com/serengil/deepface_models/releases/download/v1.0/facenet512_weights.pth",
    "facenet_weights.pth": "https://github.com/serengil/deepface_models/releases/download/v1.0/facenet_weights.pth",
    "ghostfacenet_v1.pth": "https://github.com/serengil/deepface_models/releases/download/v1.0/ghostfacenet_v1.pth",
    "openface_weights.pth": "https://github.com/serengil/deepface_models/releases/download/v1.0/openface_weights.pth",
    "res10_300x300_ssd_iter_140000.caffemodel": "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel",
    "retinaface.pth": "https://github.com/serengil/deepface_models/releases/download/v1.0/retinaface.pth",
    "shape_predictor_5_face_landmarks.dat.bz2": "http://dlib.net/files/shape_predictor_5_face_landmarks.dat.bz2",
    "vgg_face_weights.pth": "https://github.com/serengil/deepface_models/releases/download/v1.0/vgg_face_weights.pth",
    "yolov11n-face.pt": "https://github.com/YapaLab/yolo-face/releases/download/1.0.0/yolov11n-face.pt",
    "yolov11s-face.pt": "https://github.com/akanametov/yolo-face/releases/download/1.0.0/yolov11s-face.pt",
    "yolov12l-face.pt": "https://github.com/YapaLab/yolo-face/releases/download/1.0.0/yolov12l-face.pt",
    "yolov11l-face.pt": "https://github.com/akanametov/yolo-face/releases/download/1.0.0/yolov11l-face.pt",
    "yolov11m-face.pt": "https://github.com/akanametov/yolo-face/releases/download/1.0.0/yolov11m-face.pt",
    "yolov12m-face.pt": "https://github.com/YapaLab/yolo-face/releases/download/1.0.0/yolov12m-face.pt",
    "yolov12n-face.pt": "https://github.com/YapaLab/yolo-face/releases/download/1.0.0/yolov12n-face.pt",
    "yolov12s-face.pt": "https://github.com/YapaLab/yolo-face/releases/download/1.0.0/yolov12s-face.pt",
    "yolov8l-face.pt": "https://github.com/YapaLab/yolo-face/releases/download/1.0.0/yolov8l-face.pt",
    "yolov8m-face.pt": "https://github.com/YapaLab/yolo-face/releases/download/1.0.0/yolov8m-face.pt",
    "yolov8n-face.pt": "https://github.com/YapaLab/yolo-face/releases/download/1.0.0/yolov8n-face.pt",
}
