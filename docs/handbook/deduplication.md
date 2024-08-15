---
layout: default
title: Deduplication
nav_order: 2
---

# Deduplication Worlflow
{: .no_toc }

<details open markdown="block">
  <summary>
    Table of contents
  </summary>
  {: .text-delta }
- TOC
{:toc}
</details>

---

### Inference Mode Operation

This application operates in inference mode, meaning it utilizes a pre-trained model for face recognition rather than training the model itself. The pre-trained model is stored in Azure Blob Storage and is downloaded by the application upon startup. Additionally, the model can be manually updated via the admin panel.

### Model Details

The face recognition functionality is powered by the [OpenCV](https://github.com/opencv/opencv) library.

Currently, the application uses an open-source model. The model consists of two files: **deploy.prototxt** and **res10_300x300_ssd_iter_140000.caffemodel**. The model was trained using the Caffe deep learning framework and employs the Res10 architecture with a resolution of 300x300 and 140,000 iterations. This model is based on the SSD (Single Shot MultiBox Detector) methodology and is optimized for face detection tasks.

### Worklow Diagram
```mermaid
flowchart LR
  subgraph DNNManager[DNN Manager]
      direction TB
      load_model[Load Model] --> set_preferences[Set Preferences]
  end

  subgraph ImageProcessing[Image Processing]
      direction LR
      
      subgraph FaceDetection[Face Detection]
          direction TB
          load_image[Load Image] -- decoded image as 3D numpy array\n(height, width, channels of BlueGreeRed color space) --> prepare_image[Prepare Image] -- blob 4D tensor\n(normalized size, use scale factor and means) --> run_model[Run Model] -- shape (1, 1, N, 7),\n1 image\nN is the number of detected faces\neach face is described by the 7 detection values--> filter_results[Filter Results] -- confidence is above the minimum threshold\nNMS to suppress overlapping bounding boxes --> return_detections[Return Detections]
      end
      
      subgraph FaceRecognition[Face Recognition]
          direction TB
          load_image_[Load Image] --> detect_faces[Detect Faces] -- detected face regions --> generate_encodings[Generate Encodings] -- numerical representations of the facial features\n(face's geometry and appearance) --> save_encodings[Save Encodings]
      end
  end

  subgraph DuplicateFinder[Duplicate Finder]
      direction TB
      load_encodings[Load Encodings] --> compare_encodings[Compare Encodings] -- face distance less then threshold--> return_duplicates[Return Duplicates]
  end

  DNNManager --> ImageProcessing --> DuplicateFinder
  FaceDetection --> FaceRecognition

```
