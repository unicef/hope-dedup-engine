from collections.abc import Callable, Generator, Iterable
from typing import Protocol

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.deduplication.adapters import DuplicateFaceFinder

DuplicateKeyPair = tuple[str, str, float]


class DuplicateFinder(Protocol):
    weight: int

    def run(self, tracker: Callable[[int], None]) -> Generator[DuplicateKeyPair]:
        pass


def get_finders(deduplication_set: DeduplicationSet) -> Iterable[DuplicateFinder]:
    return (DuplicateFaceFinder(deduplication_set),)
