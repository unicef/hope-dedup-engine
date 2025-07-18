from collections.abc import Callable, Generator

from hope_dedup_engine.apps.api.deduplication.registry import DuplicateKeyPair
from hope_dedup_engine.apps.api.models import DeduplicationSet


class DuplicateFaceFinder:
    weight = 1

    def __init__(self, deduplication_set: DeduplicationSet):
        self.tracker = None
        self.deduplication_set = deduplication_set

    def run(self, tracker: Callable[[int], None] | None = None) -> Generator[DuplicateKeyPair]: ...
