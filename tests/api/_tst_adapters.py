from typing import Any

import pytest
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.deduplication.adapters import (
    ConfigDefaults,
    DuplicateFaceFinder,
)
from hope_dedup_engine.apps.api.models import DeduplicationSet, Image

pytestmark = pytest.mark.django_db


@pytest.fixture
def duplication_detector(mocker: MockerFixture) -> Any:
    return mocker.patch("hope_dedup_engine.apps.api.deduplication.adapters.DuplicationDetector")


def test_duplicate_face_finder_uses_duplication_detector(
    deduplication_set: DeduplicationSet,
    image: Image,
    second_image: Image,
    duplication_detector: Any,
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

    cfg = ConfigDefaults()
    cfg.apply_config_overrides(deduplication_set.config.settings)
    duplication_detector.assert_called_once_with(
        (image.filename, second_image.filename),
        cfg=cfg,
    )
    duplication_detector.return_value.find_duplicates.assert_called_once()
    assert len(found_pairs) == 1
    assert found_pairs[0] == (
        image.reference_pk,
        second_image.reference_pk,
        1 - distance,
    )
