import pytest

from hope_dedup_engine.apps.api.utils.pairs.row import (
    adjust_start,
    adjust_end,
    count_pairs,
    pairs,
    row_for,
    row_at,
    Row,
)

ROW_INDEX = 3
ROW = row_at(ROW_INDEX)


@pytest.mark.parametrize(
    ("input_row", "start", "expected_row"),
    [
        (ROW, 0, ROW),
        (ROW, 1, Row(ROW_INDEX, range(1, 4), 4)),
        (ROW, 2, Row(ROW_INDEX, range(2, 4), 4)),
        (ROW, 3, Row(ROW_INDEX, range(3, 4), 4)),
        (ROW, 4, Row(ROW_INDEX, range(4, 4), 4)),
        (ROW, 5, Row(ROW_INDEX, range(4, 4), 4)),
    ],
)
def test_adjust_start(input_row: Row, start: int, expected_row: Row) -> None:
    assert adjust_start(input_row, start) == expected_row


@pytest.mark.parametrize(
    ("input_row", "end", "expected_row"),
    [
        (ROW, 0, Row(ROW_INDEX, range(0), 4)),
        (ROW, 1, Row(ROW_INDEX, range(1), 4)),
        (ROW, 2, Row(ROW_INDEX, range(2), 4)),
        (ROW, 3, Row(ROW_INDEX, range(3), 4)),
        (ROW, 4, ROW),
        (ROW, 5, ROW),
    ],
)
def test_adjust_end(input_row: Row, end: int, expected_row: Row) -> None:
    assert adjust_end(input_row, end) == expected_row


def test_count_pairs() -> None:
    assert count_pairs(3) == 10


def test_pairs() -> None:
    assert list(pairs(ROW)) == [(0, 4), (1, 4), (2, 4), (3, 4)]


def test_row_for() -> None:
    assert row_for(7) == ROW_INDEX


def test_row_at() -> None:
    assert row_at(3) == Row(3, range(4), 4)
