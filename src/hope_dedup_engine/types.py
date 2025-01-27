from collections.abc import Iterable
from enum import Enum
from typing import Self

# from hope_dedup_engine.constants import FacialError
# TODO:
# from hope_dedup_engine.apps.api.models.deduplication import Finding as FindingModel

# .Image import StatusCode

type ReferencePK = str
type Filename = str
type Embedding = list[float]
type Score = float


class FacialError(Enum):
    GENERIC_ERROR = 999
    NO_FACE_DETECTED = 998
    MULTIPLE_FACES_DETECTED = 997
    NO_FILE_FOUND = 996


EntityImage = tuple[ReferencePK, Filename]
EntityEmbedding = tuple[ReferencePK, Embedding]
EntityEmbeddingError = tuple[ReferencePK, FacialError]
ImageEmbedding = tuple[Filename, Embedding]
ImageEmbeddingError = tuple[Filename, FacialError]
Finding = tuple[ReferencePK, ReferencePK, Score]


class SortedTuple(tuple):
    def __new__(cls, iterable: Iterable) -> Self:
        return tuple.__new__(cls, sorted(iterable))


IgnoredPair = SortedTuple[ReferencePK, ReferencePK]
