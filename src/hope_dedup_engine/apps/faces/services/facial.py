import logging
from collections.abc import Generator, Iterable
from typing import Any, cast

from deepface import DeepFace

from hope_dedup_engine.apps.faces.managers import ImagesStorageManager
from hope_dedup_engine.constants import FacialError
from hope_dedup_engine.types import (
    Embedding,
    EntityEmbedding,
    Filename,
    ImageEmbedding,
    ImageEmbeddingError,
)

logger = logging.getLogger(__name__)


def encode_faces(
    filenames: list[Filename],
    options=None,
) -> tuple[list[ImageEmbedding], list[ImageEmbeddingError]]:
    storage = ImagesStorageManager()
    images = storage.get_files()

    embeddings = []
    errors = []

    for filename in filenames:
        if filename not in images:
            errors.append((filename, FacialError.NO_FILE_FOUND))
            continue

        try:
            result = DeepFace.represent(storage.load_image(filename), **(options or {}))
            if len(result) > 1:
                errors.append((filename, FacialError.MULTIPLE_FACES_DETECTED))
            else:
                embeddings.append((filename, cast(list[float], result[0]["embedding"])))
        except TypeError as e:
            logger.exception(e)
            errors.append((filename, FacialError.GENERIC_ERROR))
        except ValueError:
            errors.append((filename, FacialError.NO_FACE_DETECTED))

    return embeddings, errors


EncodedFace = tuple[str, str | list[float]]


def face_similarity(first: Embedding, second: Embedding, **options: Any) -> float:
    result = DeepFace.verify(first, second, **options)
    return float(1 - result["distance"])


def find_similar_faces(
    encoded_pairs: Iterable[tuple[EntityEmbedding, EntityEmbedding]],
    dedupe_threshold: float,
    options: dict[str, Any],
) -> Generator[tuple[EncodedFace, EncodedFace, float]]:
    for first, second in encoded_pairs:
        _, first_embedding = first
        _, second_embedding = second
        similarity = face_similarity(first_embedding, second_embedding, **options)
        if similarity >= dedupe_threshold:
            yield first, second, similarity
