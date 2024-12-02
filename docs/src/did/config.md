The configuration can be managed directly through the **admin panel**, which provides a simple way to modify settings without changing the codebase. Navigate to:

    Home › Constance › Config

Here, you will find all the configurable settings that affect the behavior of the system, allowing for quick adjustments and better control over application behavior.

## Deep neural networks (DNN)

The deep learning component of the system is crucial for performing advanced inference tasks, including **face detection**, **face recognition**, and **finding duplicate images** using a pre-trained model. These tasks are fundamental to ensuring the accuracy and efficiency of the system in identifying and managing images.

This component relies on **Convolutional Neural Networks (CNNs)**, a type of deep learning model particularly well-suited for processing visual data. CNNs are used to automatically extract relevant features from images, such as facial landmarks and distinctive patterns, without the need for manual feature engineering.

### DNN_BACKEND

Specifies the computation backend to be used by [OpenCV](https://github.com/opencv/opencv) library for deep learning inference.

### DNN_TARGET

Specifies the target device on which [OpenCV](https://github.com/opencv/opencv) library will perform the deep learning computations.


## Face Detection

This component is responsible for locating and identifying faces in images. It uses advanced deep learning algorithms to scan images and detect the regions that contain human faces. This section outlines the key configuration parameters that influence how the face detection model processes input images and optimizes detection results.

### BLOB_FROM_IMAGE_SCALE_FACTOR

Specifies the scaling factor applied to all pixel values when converting an image to a blob. Mostly it equals 1.0 for no scaling or 1.0/255.0 and normalizing to the [0, 1] range.

Remember that scaling factor is also applied to mean values. Both scaling factor and mean values must be the same for the training and inference to get the correct results.

### BLOB_FROM_IMAGE_MEAN_VALUES

Specifies the mean BGR values used in image preprocessing to normalize pixel values by subtracting the mean values of the training dataset. This helps in reducing model bias and improving accuracy.

The specified mean values are subtracted from each channel (Blue, Green, Red) of the input image.

Remember that mean values are also applied to scaling factor. Both scaling factor and mean values must be the same for the training and inference to get the correct results.

### FACE_DETECTION_CONFIDENCE

Specifies the minimum confidence score required for a detected face to be considered valid. Detections with confidence scores below this threshold are discarded as likely false positives.

### NMS_THRESHOLD

Specifies the Intersection over Union (IoU) threshold used in Non-Maximum Suppression (NMS) to filter out overlapping bounding boxes. If the IoU between two boxes exceeds this threshold, the box with the lower confidence score is suppressed. Lower values result in fewer, more distinct boxes; higher values allow more overlapping boxes to remain.

## Face Recognition

This component builds on face detection to identify and differentiate between individual faces. This involves generating face encodings, which are numerical representations of the unique facial features used for recognition. These encodings can then be compared to determine if two images contain the same person or to find matches in a database of known faces.

### FACE_ENCODINGS_NUM_JITTERS

Specifies the number of times to re-sample the face when calculating the encoding. Higher values increase accuracy but are computationally more expensive and slower. For example, setting 'num_jitters' to 100 makes the process 100 times slower.

### FACE_ENCODINGS_MODEL

Specifies the model type used for encoding face landmarks. It can be either 'small' which is faster and  only 5 key facial landmarks, or 'large' which is more precise and identifies 68 key facial landmarks but requires more computational resources.


## Duplicate Finder

This component is responsible for identifying duplicate images in the system by comparing face embeddings. These embeddings are numerical representations of facial features generated during the face recognition process. By calculating the distance between the embeddings of different images, the system can determine whether two images contain the same person, helping in the identification and removal of duplicates or grouping similar faces together.

### FACE_DISTANCE_THRESHOLD

Specifies the maximum allowable distance between two face embeddings for them to be considered a match. It helps determine if two faces belong to the same person by setting a threshold for similarity. Lower values result in stricter matching, while higher values allow for more lenient matches.

