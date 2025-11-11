from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.utils.pairs.row import row_at
from hope_dedup_engine.apps.api.utils.pairs.rows import adjust_start, adjust_end, rows_from_pair_range, pairs


def test_adjust_start_nothing_changes_on_empty_rows(mocker: MockerFixture) -> None:
    adjust_row_start_mock = mocker.patch("hope_dedup_engine.apps.api.utils.pairs.rows.adjust_row_start")
    adjust_start([], 0)
    adjust_row_start_mock.assert_not_called()


def test_adjust_start(mocker: MockerFixture) -> None:
    adjust_row_start_mock = mocker.patch("hope_dedup_engine.apps.api.utils.pairs.rows.adjust_row_start")
    adjust_start([row := row_at(0)], start := 0)
    adjust_row_start_mock.assert_called_once_with(row, start)


def test_adjust_end_nothing_changes_on_empty_rows(mocker: MockerFixture) -> None:
    adjust_row_end_mock = mocker.patch("hope_dedup_engine.apps.api.utils.pairs.rows.adjust_row_end")
    adjust_end([], 0)
    adjust_row_end_mock.assert_not_called()


def test_adjust_end(mocker: MockerFixture) -> None:
    adjust_row_end_mock = mocker.patch("hope_dedup_engine.apps.api.utils.pairs.rows.adjust_row_end")
    adjust_end([row := row_at(0)], end := 0)
    adjust_row_end_mock.assert_called_once_with(row, end)


def test_rows_from_pair_range() -> None:
    assert rows_from_pair_range(0, 6) == (row_at(0), row_at(1), row_at(2))


def test_pairs() -> None:
    assert list(pairs((row_at(0),))) == [(0, 1)]
