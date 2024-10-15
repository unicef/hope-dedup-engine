from django.conf import settings
from django.core.files.storage import FileSystemStorage

from constance import config
from cv2 import dnn, dnn_Net


class DNNInferenceManager:
    """
    A class to manage the loading and configuration of a neural network model using OpenCV's DNN module.

    The DNNInferenceManager class provides functionality to load a neural network model from Caffe files stored in a
    specified storage and configure the model with preferred backend and target settings.
    """

    def __init__(self, storage: FileSystemStorage) -> None:
        """
        Loads and configures the neural network model using the specified storage.

        Args:
            storage (FileSystemStorage): The storage object from which to load the neural network model.
        """
        self.net = dnn.readNetFromCaffe(
            storage.path(settings.DNN_FILES.get("prototxt").get("filename")),
            storage.path(settings.DNN_FILES.get("caffemodel").get("filename")),
        )
        self.net.setPreferableBackend(int(config.DNN_BACKEND))
        self.net.setPreferableTarget(int(config.DNN_TARGET))

    def get_model(self) -> dnn_Net:
        """
        Get the loaded and configured neural network model.

        Returns:
            cv2.dnn_Net: The neural network model loaded and configured by this manager.
        """
        return self.net
