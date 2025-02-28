from collections.abc import Callable, Generator

from hope_dedup_engine.apps.api.deduplication.registry import DuplicateKeyPair
from hope_dedup_engine.apps.api.models import DeduplicationSet


class DuplicateFaceFinder:
    weight = 1

    def __init__(self, deduplication_set: DeduplicationSet):
        self.tracker = None
        self.deduplication_set = deduplication_set

    def run(self, tracker: Callable[[int], None] | None = None) -> Generator[DuplicateKeyPair, None, None]:
        ...
        # filename_to_reference_pk = {
        #     filename: reference_pk
        #     for reference_pk, filename in self.deduplication_set.image_set.values_list(
        #         "reference_pk", "filename"
        #     )
        # }
        # options = {
        #     "detector_backend": config.FACE_DETECTOR_MODEL,
        #     "model_name": config.FACIAL_RECOGNITION_MODEL,
        # }
        # # options = ConfigDefaults()
        # # if self.deduplication_set.config:
        # #     options.apply_config_overrides(self.deduplication_set.config.settings)
        # # ignored key pairs are not handled correctly in DuplicationDetector
        # detector = FacialDetector(
        #     self.deduplication_set.pk,
        #     tuple[str](filename_to_reference_pk.keys()),
        #     options=options,
        # )
        # for first_filename, second_filename, distance in detector.find_duplicates(
        #     # tracker
        # ):
        #     yield (
        #         filename_to_reference_pk[first_filename],
        #         (
        #             filename_to_reference_pk[second_filename]
        #             if second_filename in filename_to_reference_pk
        #             else second_filename
        #         ),
        #         distance if is_facial_error(distance) else (1 - distance),
        #     )
