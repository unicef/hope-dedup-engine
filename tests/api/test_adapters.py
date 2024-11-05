from unittest.mock import MagicMock

from pytest import fixture
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.deduplication.adapters import DuplicateFaceFinder
from hope_dedup_engine.apps.api.models import DeduplicationSet, Image


@fixture
def duplication_detector(mocker: MockerFixture) -> MagicMock:
    yield mocker.patch(
        "hope_dedup_engine.apps.api.deduplication.adapters.DuplicationDetector"
    )


def test_duplicate_face_finder_uses_duplication_detector(
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
    duplication_detector: MagicMock,
) -> None:
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
        deduplication_set.config.settings,
    )
    duplication_detector.return_value.find_duplicates.assert_called_once()
    assert len(found_pairs) == 1
    assert found_pairs[0] == (
        image.reference_pk,
        second_image.reference_pk,
        1 - distance,
    )


def _run_duplicate_face_finder(deduplication_set: DeduplicationSet) -> None:
    finder = DuplicateFaceFinder(deduplication_set)
    tuple(finder.run())  # tuple is used to make generator finish execution


def test_duplication_detector_is_initiated_with_correct_face_distance_threshold_value(
    deduplication_set: DeduplicationSet,
    duplication_detector: MagicMock,
) -> None:
    # deduplication set face_distance_threshold config value is used
    _run_duplicate_face_finder(deduplication_set)
    duplication_detector.assert_called_once_with((), deduplication_set.config.settings)
    duplication_detector.reset_mock()
    deduplication_set.config = None
    _run_duplicate_face_finder(deduplication_set)
    duplication_detector.assert_called_once_with((), {})
