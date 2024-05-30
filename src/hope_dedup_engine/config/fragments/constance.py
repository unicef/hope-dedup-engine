import cv2

from hope_dedup_engine.apps.security.constants import DEFAULT_GROUP_NAME

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

CONSTANCE_CONFIG = {
    "NEW_USER_IS_STAFF": (False, "Set any new user as staff", bool),
    "NEW_USER_DEFAULT_GROUP": (DEFAULT_GROUP_NAME, "Group to assign to any new user", str),
    "DNN_BACKEND": (
        cv2.dnn.DNN_BACKEND_OPENCV,
        "Specifies the computation backend to be used by OpenCV for deep learning inference.",
        "dnn_backend",
    ),
    "DNN_TARGET": (
        cv2.dnn.DNN_TARGET_CPU,
        "Specifies the target device on which OpenCV will perform the deep learning computations.",
        "dnn_target",
    ),
    "SCALE_FACTOR": (
        1.0,
        """Specifies the scaling factor applied to all pixel values when converting an image to a blob. Mostly
        it equals 1.0 for no scaling or 1.0/255.0 and normalizing to the [0, 1] range.
        Remember that mean values are also applied to scaling factor. Both scaling factor and mean values
        must be the same for the training and inference to get the correct results.
        """,
        float,
    ),
    "MEAN_VALUES": (
        "104.0, 177.0, 123.0",
        """Specifies the mean BGR values used in image preprocessing to normalize pixel values by subtracting
        the mean values of the training dataset. This helps in reducing model bias and improving accuracy.
        The specified mean values are subtracted from each channel (Blue, Green, Red) of the input image.
        Remember that mean values are also applied to scaling factor. Both scaling factor and mean values
        must be the same for the training and inference to get the correct results.
        """,
        "tuple_field",
    ),
    "FACE_DETECTION_CONFIDENCE": (
        0.7,
        """
        Specifies the minimum confidence score required for a detected face to be considered valid. Detections
        with confidence scores below this threshold are discarded as likely false positives.
        """,
        float,
    ),
    "NMS_THRESHOLD": (
        0.4,
        """
        Specifies the Intersection over Union (IoU) threshold used in Non-Maximum Suppression (NMS) to filter out
        overlapping bounding boxes. If the IoU between two boxes exceeds this threshold, the box with the lower
        confidence score is suppressed. Lower values result in fewer, more distinct boxes; higher values allow more
        overlapping boxes to remain.
        """,
        float,
    ),
    "DISTANCE_THRESHOLD": (
        0.5,
        """
        Specifies the maximum allowable distance between two face embeddings for them to be considered a match. It helps
        determine if two faces belong to the same person by setting a threshold for similarity. Lower values result in
        stricter matching, while higher values allow for more lenient matches.
        """,
        float,
    ),
    "FACE_DETECTION_MODEL": (
        "hog",
        """
        Specifies the model type used for face detection. It can be either faster 'hog'(Histogram of Oriented Gradients)
        or more accurate 'cnn'(Convolutional Neural Network).",
        """,
        "face_detection_model",
    ),
}


CONSTANCE_CONFIG_FIELDSETS = {
    "User settings": {
        "fields": ("NEW_USER_IS_STAFF", "NEW_USER_DEFAULT_GROUP"),
        "collapse": False,
    },
    "Face recognition settings": {
        "fields": (
            "DNN_BACKEND",
            "DNN_TARGET",
            "SCALE_FACTOR",
            "MEAN_VALUES",
            "FACE_DETECTION_CONFIDENCE",
            "NMS_THRESHOLD",
            "DISTANCE_THRESHOLD",
            "FACE_DETECTION_MODEL",
        ),
        "collapse": False,
    },
}

CONSTANCE_ADDITIONAL_FIELDS = {
    "email": [
        "django.forms.EmailField",
        {},
    ],
    "dnn_backend": [
        "django.forms.ChoiceField",
        {
            "choices": ((cv2.dnn.DNN_BACKEND_OPENCV, "DNN_BACKEND_OPENCV"),),
        },
    ],
    "dnn_target": [
        "django.forms.ChoiceField",
        {
            "choices": ((cv2.dnn.DNN_TARGET_CPU, "DNN_TARGET_CPU"),),
        },
    ],
    "face_detection_model": [
        "django.forms.ChoiceField",
        {
            "choices": (("hog", "HOG"), ("cnn", "CNN")),
        },
    ],
    "tuple_field": ["hope_dedup_engine.apps.faces.validators.MeanValuesTupleField", {}],
}
