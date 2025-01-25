from collections.abc import Iterable
from typing import Self

from hope_dedup_engine.constants import FacialError

ReferencePK = str
Filename = str
Embedding = list[float]
Score = float

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
