from django.conf import settings

from constance import config
from cv2 import dnn, dnn_Net

from hope_dedup_engine.apps.core.storage import CV2DNNStorage


class DNNInferenceManager:
    """
    A class to manage the loading and configuration of a neural network model using OpenCV's DNN module.

    The DNNInferenceManager class provides functionality to load a neural network model from Caffe files stored in a
    specified storage and configure the model with preferred backend and target settings.
    """

    def __init__(self, storage: CV2DNNStorage) -> None:
        """
        Loads and configures the neural network model using the specified storage.

        Args:
            storage (CV2DNNStorage): The storage object from which to load the neural network model.
        """
        self.net = dnn.readNetFromCaffe(
            storage.path(settings.PROTOTXT_FILE),
            storage.path(settings.CAFFEMODEL_FILE),
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
