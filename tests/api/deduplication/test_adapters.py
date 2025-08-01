import pytest
from unittest.mock import Mock

from hope_dedup_engine.apps.api.deduplication.adapters import DuplicateFaceFinder
from hope_dedup_engine.apps.api.models import DeduplicationSet


@pytest.mark.api
def test_duplicate_face_finder_init():
    """Test that DuplicateFaceFinder is initialized correctly."""
    mock_dedup_set = Mock(spec=DeduplicationSet)
    finder = DuplicateFaceFinder(deduplication_set=mock_dedup_set)

    assert finder.deduplication_set is mock_dedup_set
    assert finder.tracker is None
    assert finder.weight == 1


@pytest.mark.api
def test_duplicate_face_finder_run_is_not_implemented():
    """Test that the run method is not implemented."""
    mock_dedup_set = Mock(spec=DeduplicationSet)
    finder = DuplicateFaceFinder(deduplication_set=mock_dedup_set)
    assert finder.run() is None
