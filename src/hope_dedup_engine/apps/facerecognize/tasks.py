import logging
import pickle
from typing import Dict, List, Tuple

import cv2
import face_recognition
from celery import shared_task

from hope_dedup_engine.apps.core.storage import DataSetStorage
from hope_dedup_engine.apps.facerecognize.models import DeduplicationResult, DeduplicationTask
from hope_dedup_engine.apps.facerecognize.utils import DEFAULT_ENCODINGS_PATH, encode_faces, get_face_detections_dnn

logger = logging.getLogger(__name__)


def load_encodings():
    with DataSetStorage.open(DEFAULT_ENCODINGS_PATH, "rb") as file:
        encodings = pickle.load(file)
    return encodings


@shared_task
def deduplicate_faces(hope_data: List[Tuple[str, str]]) -> List[Dict[str, str]]:
    media_storage = DataSetStorage()
    encodings_data = load_encodings()
    task = DeduplicationTask.objects.create(status="PENDING")
    results: List[Dict[str, str]] = []
    for uuid, image_path in hope_data:
        try:
            with media_storage.open(image_path) as image_file:
                image = cv2.imread(image_file.name)
                regions = get_face_detections_dnn(image)

                if regions:
                    _, encodings = encode_faces(image, regions)

                    for encoding in encodings:  # Process all detected face encodings
                        # Compare with existing encodings
                        for other_uuid, other_encodings in encodings_data.items():
                            for other_encoding in other_encodings:
                                distance = face_recognition.face_distance([encoding], other_encoding)[0]
                                if distance < 0.8:
                                    DeduplicationResult.objects.create(
                                        task=task, uuid1=uuid, uuid2=other_uuid, similarity_score=distance
                                    )
                                results.append({"uuid1": uuid, "uuid2": other_uuid, "similarity_score": distance})
                        encodings_data.setdefault(uuid, []).append(encoding)
                else:
                    logger.warning(f"No faces detected for {image_path}")

        except Exception as e:
            logger.error(f"Error processing {uuid}, {image_path}: {e}")

    # Save updated encodings data
    with DataSetStorage.open(DEFAULT_ENCODINGS_PATH, "wb") as file:
        pickle.dump(encodings_data, file)
        task.status = "COMPLETED"  # Mark the task as completed
        task.save()
    return {"task_id": task.task_id, "results": results}
