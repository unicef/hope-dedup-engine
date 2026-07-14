# Application Settings

Beyond environment variables, runtime behavior is tuned in the admin panel on two levels: **global defaults** and **per-group settings**.

## Global defaults (Constance)

Navigate to:

    Home › Constance › Config

These values are managed with [django-constance](https://django-constance.readthedocs.io/) and take effect without redeploying. They are the *defaults* for new deduplication set groups — each group snapshots them at creation time, so changing a default does **not** affect existing groups.

### Face detection and recognition

| Key | Default | Description |
|-----|---------|-------------|
| `DEFAULT_RECOGNITION_MODEL` | `Facenet512` | Face recognition model used to encode faces. Choices include Facenet512, Facenet, VGG-Face, ArcFace, OpenFace, DeepID, Dlib, SFace, GhostFaceNet. |
| `DEFAULT_DETECTOR_BACKEND` | `retinaface` | Face detector. Choices include retinaface, mtcnn, ssd, dlib, mediapipe, opencv, various YOLO versions, centerface. |
| `DEFAULT_DISTANCE_METRIC` | `cosine` | Similarity metric for comparing embeddings (cosine, euclidean, euclidean_l2, angular). |
| `DEFAULT_FACE_DETECTION_CONFIDENCE_THRESHOLD` | `0.90` | Minimum detector confidence for a face to be accepted. |
| `DEFAULT_DUPLICATE_CONFIDENCE_THRESHOLD` | `0.5` | Minimum match confidence for reporting a duplicate pair. |
| `DEFAULT_SHARPNESS_THRESHOLD` … `DEFAULT_UNIFIED_QUALITY_SCORE_THRESHOLD` | `0.0` (disabled) | The six OFIQ image-quality thresholds — see the [pipeline](../concepts/pipeline.md#stage-1-image-quality-assessment-ofiq). |

!!! warning "Changing the model requires weights"
    If you switch `DEFAULT_RECOGNITION_MODEL` or `DEFAULT_DETECTOR_BACKEND`, make sure the corresponding weight files are available under `DEEPFACE_HOME`. DeepFace downloads missing weights automatically on first use, but this may take time and requires network access from the worker containers.

### Other keys

| Key | Description |
|-----|-------------|
| `HOPE_API_TOKEN` | Token attached to outbound webhook notifications (masked in the UI). |
| `NEW_USER_IS_STAFF` | Whether newly created users (e.g. via SSO) get staff status. |
| `NEW_USER_DEFAULT_GROUP` | Permission group automatically assigned to new users. |

## Per-group settings

Navigate to:

    Home › Api › Deduplication set groups › <group>

Each group stores its own copy of the deduplication settings (thresholds only — model, detector, and metric currently follow the group's snapshot of the defaults). The same values are exposed to clients through the [config API endpoint](../integration/configuration.md).

The admin form enforces the same rules as the API:

- settings cannot be changed while a processing job is running in the group;
- settings cannot be changed once the group contains an **approved** deduplication set;
- when settings change and a set is in `Encoded`/`Deduplicated` state, that set's embeddings and findings are cleared and it returns to `Ready` for re-processing.

## API permission

API access requires the `api | deduplication set | Can use api` permission on the token's user (usually granted via a permission group). Additional object-level permissions exist for admin actions (clear embeddings, export findings, process encodings/deduplication, remove findings, view finding details).
