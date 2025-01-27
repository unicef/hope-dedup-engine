from collections.abc import Iterable
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from hope_dedup_engine.apps.api.models.deduplication import (  # noqa: F401
        Finding as FindingModel,
    )


type ReferencePK = str
type Filename = str
type Embedding = list[float]
type Score = float


EntityImage = tuple[ReferencePK, Filename]
EntityEmbedding = tuple[ReferencePK, Embedding]
EntityEmbeddingError = tuple[ReferencePK, "FindingModel.StatusCode"]
ImageEmbedding = tuple[Filename, Embedding]
ImageEmbeddingError = tuple[Filename, "FindingModel.StatusCode"]


class SortedTuple(tuple):
    def __new__(cls, iterable: Iterable) -> Self:
        return tuple.__new__(cls, sorted(iterable))


EntityIgnoredPair = SortedTuple[ReferencePK, ReferencePK]
