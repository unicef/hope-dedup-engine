from collections.abc import Callable, Generator, Iterable
from typing import Protocol

from hope_dedup_engine.apps.api.models import DeduplicationSet

DuplicateKeyPair = tuple[str, str, float]


class DuplicateFinder(Protocol):
    weight: int

    def run(self, tracker: Callable[[int], None]) -> Generator[DuplicateKeyPair]:
        pass


def get_finders(deduplication_set: DeduplicationSet) -> Iterable[DuplicateFinder]:
    # we have to import it here to solve a circular import issue.
    from hope_dedup_engine.apps.api.deduplication.adapters import DuplicateFaceFinder  # noqa: PLC0415

    return (DuplicateFaceFinder(deduplication_set),)
