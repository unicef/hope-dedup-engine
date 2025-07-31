import pytest
from unittest.mock import Mock

from hope_dedup_engine.apps.api.deduplication.adapters import DuplicateFaceFinder
from hope_dedup_engine.apps.api.models import DeduplicationSet


@pytest.mark.api
class TestDuplicateFaceFinder:
    def test_init(self):
        """Test that DuplicateFaceFinder is initialized correctly."""
        mock_dedup_set = Mock(spec=DeduplicationSet)
        finder = DuplicateFaceFinder(deduplication_set=mock_dedup_set)

        assert finder.deduplication_set is mock_dedup_set
        assert finder.tracker is None
        assert finder.weight == 1

    def test_run_is_not_implemented(self):
        """Test that the run method is not implemented."""
        mock_dedup_set = Mock(spec=DeduplicationSet)
        finder = DuplicateFaceFinder(deduplication_set=mock_dedup_set)

        # The method body is '...', which returns an Ellipsis object when called.
        # This indicates it's a placeholder for a real implementation.
        assert finder.run() is ...
