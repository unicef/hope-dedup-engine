from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.deduplication.adapters import DuplicateFaceFinder
from hope_dedup_engine.apps.api.models import DeduplicationSet, Image


def test_duplicate_face_finder_uses_duplication_detector(
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
    mocker: MockerFixture,
) -> None:
    duplication_detector = mocker.patch(
        "hope_dedup_engine.apps.api.deduplication.adapters.DuplicationDetector"
    )
    duplication_detector.return_value.find_duplicates.return_value = iter(
        (
            (
                image.filename,
                second_image.filename,
                distance := 0.5,
            ),
        )
    )

    finder = DuplicateFaceFinder(deduplication_set)
    found_pairs = tuple(finder.run())

    duplication_detector.assert_called_once_with(
        (image.filename, second_image.filename),
        deduplication_set.config.face_distance_threshold,
    )
    duplication_detector.return_value.find_duplicates.assert_called_once()
    assert len(found_pairs) == 1
    assert found_pairs[0] == (
        image.reference_pk,
        second_image.reference_pk,
        1 - distance,
    )
