from collections.abc import Generator
from itertools import combinations

from hope_dedup_engine.apps.api.deduplication.registry import DuplicateKeyPair
from hope_dedup_engine.apps.api.models import DeduplicationSet


class AllDuplicateFinder:
    weight = 1

    def __init__(self, deduplication_set: DeduplicationSet) -> None:
        self.deduplication_set = deduplication_set

    def run(self) -> Generator[DuplicateKeyPair, None, None]:
        reference_pks = self.deduplication_set.image_set.values_list(
            "reference_pk", flat=True
        ).order_by("reference_pk")
        for first, second in combinations(reference_pks, 2):
            yield first, second, 1.0


class NoDuplicateFinder:
    weight = 1

    def run(self) -> Generator[DuplicateKeyPair, None, None]:
        # empty generator
        return
        yield


class FailingDuplicateFinder:
    weight = 1

    def run(self) -> Generator[DuplicateKeyPair, None, None]:
        raise Exception
