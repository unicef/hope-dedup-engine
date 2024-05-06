import cv2

from hope_dedup_engine.config import settings

IMAGES_PATH = settings.DATASET_PATH / "images"
ENCODED_PATH = settings.DATASET_PATH / "encoded"
PROTOTXT_FILE = settings.DATASET_PATH / "deploy.prototxt"
CAFFEMODEL_FILE = settings.DATASET_PATH / "res10_300x300_ssd_iter_140000.caffemodel"

DNN_BACKEND = cv2.dnn.DNN_TARGET_CPU
DNN_TARGET = cv2.dnn.DNN_TARGET_CPU

DISTANCE_THRESHOLD = 0.4
