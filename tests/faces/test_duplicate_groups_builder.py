from unittest.mock import MagicMock, patch

import pytest

from hope_dedup_engine.apps.faces.utils.duplicate_groups_builder import DuplicateGroupsBuilder


@pytest.mark.parametrize(
    "checked, threshold, expected_groups",
    [
        ({("path1", "path2", 0.2), ("path2", "path3", 0.1)}, 0.3, (("path1", "path2"), ("path3", "path2"))),
        ({("path1", "path2", 0.2), ("path2", "path3", 0.4)}, 0.3, (("path1", "path2"),)),
        ({("path1", "path2", 0.4), ("path2", "path3", 0.4)}, 0.3, ()),
        (
            {("path1", "path2", 0.2), ("path2", "path3", 0.2), ("path3", "path4", 0.2)},
            0.3,
            (("path4", "path3"), ("path1", "path2")),
        ),
    ],
)
def test_duplicate_groups_builder(checked, threshold, expected_groups):
    def sort_nested_tuples(nested_tuples: tuple[tuple[str]]) -> tuple[tuple[str]]:
        sorted_inner = tuple(tuple(sorted(inner_tuple)) for inner_tuple in nested_tuples)
        sorted_outer = tuple(sorted(sorted_inner))
        return sorted_outer

    mock_config = MagicMock()
    mock_config.FACE_DISTANCE_THRESHOLD = threshold
    with patch("hope_dedup_engine.apps.faces.utils.duplicate_groups_builder.config", mock_config):
        DuplicateGroupsBuilder.build(checked)
