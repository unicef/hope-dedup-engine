from collections.abc import Generator

from hope_dedup_engine.apps.api.deduplication.registry import DuplicateKeyPair
from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.faces.services.duplication_detector import (
    DuplicationDetector,
)


class DuplicateFaceFinder:
    weight = 1

    def __init__(self, deduplication_set: DeduplicationSet):
        self.deduplication_set = deduplication_set

    def run(self) -> Generator[DuplicateKeyPair, None, None]:
        filename_to_reference_pk = {
            filename: reference_pk
            for reference_pk, filename in self.deduplication_set.image_set.values_list(
                "reference_pk", "filename"
            )
        }
        # ignored key pairs are not handled correctly in DuplicationDetector
        detector = DuplicationDetector(tuple[str](filename_to_reference_pk.keys()), ())
        for first_filename, second_filename, distance in detector.find_duplicates():
            yield filename_to_reference_pk[first_filename], filename_to_reference_pk[
                second_filename
            ], 1 - distance