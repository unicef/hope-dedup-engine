from collections.abc import Iterable
from typing import Self

from hope_dedup_engine.constants import FacialError

type ReferencePK = str
type Filename = str
type Embedding = list[float]
type Score = float

type EntityImage = tuple[ReferencePK, Filename]
type EntityEmbedding = tuple[ReferencePK, Embedding]
type EntityEmbeddingError = tuple[ReferencePK, FacialError]
type ImageEmbedding = tuple[Filename, Embedding]
type ImageEmbeddingError = tuple[Filename, FacialError]
type Finding = tuple[ReferencePK, ReferencePK, Score]


class SortedTuple(tuple):
    def __new__(cls, iterable: Iterable) -> Self:
        return tuple.__new__(cls, sorted(iterable))


IgnoredPair = SortedTuple[ReferencePK, ReferencePK]
