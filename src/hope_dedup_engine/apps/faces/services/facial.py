import logging

import cv2
import numpy as np
from deepface import DeepFace
from django.conf import settings
from storages.backends.azure_storage import AzureStorage

from hope_dedup_engine.apps.api.models import Image

logger = logging.getLogger(__name__)


def encode_faces(files: list[str], options: dict | None = None, progress=None) -> dict:
    """Generate face embeddings from image files by processing them in memory.

    This function downloads image files from Azure Blob Storage into memory,
    decodes them, and uses DeepFace to generate embeddings without writing
    to the local filesystem.

    Args:
        files (list[str]): A list of filenames (blob names) to process.
        options (dict, optional): A dictionary of options to pass to DeepFace.represent().
        progress (callable, optional): A callback function for reporting progress.

    Returns:
        dict: A dictionary mapping filenames to their face embedding (a list of floats)
              or an error status string (e.g., 'NO_FACE_DETECTED').

    """
    if not callable(progress):
        progress = lambda *a, **kw: None

    model_options = {
        "model_name": "ArcFace",
        "detector_backend": "retinaface",
    }
    if options:
        model_options.update(options)

    results = {}
    remote_storage = AzureStorage(**settings.STORAGES.get("hope").get("OPTIONS"))

    for n, filename in enumerate(files):
        progress(current_step=n, current_file=filename)
        try:
            with remote_storage.open(filename, "rb") as remote_file:
                file_content = remote_file.read()

            np_arr = np.frombuffer(file_content, np.uint8)
            img_np = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if img_np is None:
                raise ValueError(f"Image could not be decoded: {filename}")
            embedding_objs = DeepFace.represent(
                img_path=img_np,
                model_name=model_options["model_name"],
                detector_backend=model_options["detector_backend"],
            )

            if len(embedding_objs) > 1:
                results[filename] = Image.StatusCode.MULTIPLE_FACES_DETECTED.name
            else:
                results[filename] = embedding_objs[0]["embedding"]

        except FileNotFoundError:
            results[filename] = Image.StatusCode.NO_FILE_FOUND.name
        except ValueError as e:
            if "Face could not be detected" in str(e):
                results[filename] = Image.StatusCode.NO_FACE_DETECTED.name
            else:
                logger.warning("ValueError during face encoding for %s: %s", filename, e)
                results[filename] = Image.StatusCode.GENERIC_ERROR.name
        except Exception as e:
            logger.exception("Unexpected error during face encoding for %s: %s", filename, e)
            results[filename] = Image.StatusCode.GENERIC_ERROR.name

    return results
