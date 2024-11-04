from hope_dedup_engine.apps.api.deduplication.adapters import DuplicateFaceFinder
from hope_dedup_engine.apps.api.deduplication.registry import get_finders
from hope_dedup_engine.apps.api.models import DeduplicationSet


def test_get_finders_returns_duplicate_face_finder(
    deduplication_set: DeduplicationSet,
) -> None:
    assert any(
        isinstance(finder, DuplicateFaceFinder)
        for finder in get_finders(deduplication_set)
    )
