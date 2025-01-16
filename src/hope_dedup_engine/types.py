from collections.abc import Iterable
from typing import Self

# from hope_dedup_engine.constants import FacialError
# TODO:
from hope_dedup_engine.api.models.deduplication.Finding import StatusCode

type ReferencePK = str
type Filename = str
type Embedding = list[float]
type Score = float

EntityImage = tuple[ReferencePK, Filename]
EntityEmbedding = tuple[ReferencePK, Embedding]
EntityEmbeddingError = tuple[ReferencePK, StatusCode]
ImageEmbedding = tuple[Filename, Embedding]
ImageEmbeddingError = tuple[Filename, StatusCode]
Finding = tuple[ReferencePK, ReferencePK, Score]


class SortedTuple(tuple):
    def __new__(cls, iterable: Iterable) -> Self:
        return tuple.__new__(cls, sorted(iterable))


IgnoredPair = SortedTuple[ReferencePK, ReferencePK]
