import pytest

from hope_dedup_engine.apps.api.utils.pairs.query import flatten_indices, is_none, slices_and_ranges
from hope_dedup_engine.apps.api.utils.pairs.row import Row
from hope_dedup_engine.apps.api.utils.pairs.rows import rows_from_pair_range


def test_flatten_indices() -> None:
    rows = rows_from_pair_range(5, 7)
    assert flatten_indices(rows) == (0, None, 2, 3, 4)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        (1, False),
    ],
)
def test_is_none(value: int | None, expected: bool) -> None:
    assert is_none(value) is expected


def test_slices_and_ranges() -> None:
    assert tuple(slices_and_ranges((Row(2, range(2, 3), 3), Row(3, range(1), 4)))) == (
        (slice(0, 1), range(1)),
        (slice(2, 5), range(2, 5)),
    )
