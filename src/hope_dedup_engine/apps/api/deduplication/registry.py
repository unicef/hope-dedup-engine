from collections.abc import Callable, Generator, Iterable
from typing import Protocol

from hope_dedup_engine.apps.api.models import DeduplicationSet

DuplicateKeyPair = tuple[str, str, float]


class DuplicateFinder(Protocol):
    weight: int

    def run(self, tracker: Callable[[int], None]) -> Generator[DuplicateKeyPair, None, None]: ...


def get_finders(deduplication_set: DeduplicationSet) -> Iterable[DuplicateFinder]:
    from hope_dedup_engine.apps.api.deduplication.adapters import DuplicateFaceFinder

    return (DuplicateFaceFinder(deduplication_set),)
