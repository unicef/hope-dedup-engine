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

IgnoredPair = tuple[ReferencePK, ReferencePK]
