import logging

from azure.core.exceptions import ResourceNotFoundError
from deepface import DeepFace

from hope_dedup_engine.apps.api.models import Image
from hope_dedup_engine.apps.faces.managers import ImagesStorageManager
from hope_dedup_engine.apps.faces.utils import report_long_execution
from hope_dedup_engine.type_aliases import EncodingType

logger = logging.getLogger(__name__)


def default_progress(*args):
    return True


def encode_faces(
    files: list[str],
    options: dict | None = None,
    progress=None,
) -> EncodingType:
    if not callable(progress):
        progress = default_progress

    with report_long_execution("ImagesStorageManager()"):
        storage = ImagesStorageManager()

    encoded = {}
    for file in files:
        with report_long_execution("progress()"):
            progress()
        try:
            # Ensure a pgvector-compatible model is used by default.
            model_options = options or {}
            model_options.setdefault("model_name", "ArcFace")

            with report_long_execution(f"DeepFace.represent(..., model_name='{model_options['model_name']}')"):
                result = DeepFace.represent(storage.load_image(file), **model_options)
            if len(result) > 1:
                encoded[file] = Image.StatusCode.MULTIPLE_FACES_DETECTED.name
            else:
                encoded[file] = result[0]["embedding"]
        except TypeError as e:
            logger.exception(e)
            encoded[file] = Image.StatusCode.GENERIC_ERROR.name
        except ValueError:
            encoded[file] = Image.StatusCode.NO_FACE_DETECTED.name
        except ResourceNotFoundError:
            encoded[file] = Image.StatusCode.NO_FILE_FOUND.name

    return encoded
