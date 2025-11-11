import pytest
from django.db.models import QuerySet
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.utils.pairs.query import (
    flatten_indices,
    is_none,
    slices_and_ranges,
    load_models,
    count_pairs,
    calculate_chunks,
    pairs,
)
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


def test_load_models(mocker: MockerFixture) -> None:
    query_set_mock = mocker.MagicMock(spec=QuerySet)
    query_set_mock.__getitem__.side_effect = (
        (model0 := mocker.Mock(),),
        (model2 := mocker.Mock(), model3 := mocker.Mock(), model4 := mocker.Mock()),
    )
    slices_and_ranges_mock = mocker.patch("hope_dedup_engine.apps.api.utils.pairs.query.slices_and_ranges")
    slices_and_ranges_mock.return_value = (
        (slice0 := slice(0, 1), range(1)),
        (slice1 := slice(2, 5), range(2, 5)),
    )
    rows = Row(2, range(2, 3), 3), Row(3, range(1), 4)

    assert load_models(query_set_mock, rows) == {
        0: model0,
        2: model2,
        3: model3,
        4: model4,
    }
    query_set_mock.__getitem__.assert_has_calls(
        (
            mocker.call(slice0),
            mocker.call(slice1),
        )
    )
    slices_and_ranges_mock.assert_called_once_with(rows)


def test_count_pairs(mocker: MockerFixture) -> None:
    query_set_mock = mocker.Mock(spec=QuerySet)
    number_of_records = 3
    query_set_mock.count.return_value = number_of_records
    count_pairs_for_row_mock = mocker.patch("hope_dedup_engine.apps.api.utils.pairs.query.count_pairs_for_row")
    count_pairs_for_row_mock.return_value = 3

    assert count_pairs(query_set_mock) == 3
    query_set_mock.count.assert_called_once()
    count_pairs_for_row_mock.assert_called_once_with(number_of_records - 2)


def test_calculate_chunks() -> None:
    assert tuple(calculate_chunks(10, 2, 3)) == (
        (2, 5),
        (5, 8),
        (8, 10),
    )


def test_pairs_query_not_ordered(mocker: MockerFixture) -> None:
    query_set_mock = mocker.Mock(spec=QuerySet)
    query_set_mock.ordered = False
    with pytest.raises(ValueError, match="QuerySet must be ordered"):
        tuple(pairs(query_set_mock, 0, 42))


def test_pairs_query(mocker: MockerFixture) -> None:
    query_set_mock = mocker.Mock(spec=QuerySet)
    query_set_mock.ordered = True
    rows_from_pair_range_mock = mocker.patch("hope_dedup_engine.apps.api.utils.pairs.query.rows_from_pair_range")
    rows_from_pair_range_mock.return_value = (
        Row(0, range(1), 1),
        Row(1, range(2), 2),
    )
    load_models_mock = mocker.patch("hope_dedup_engine.apps.api.utils.pairs.query.load_models")
    load_models_mock.return_value = {
        0: (item0 := mocker.Mock()),
        1: (item1 := mocker.Mock()),
        2: (item2 := mocker.Mock()),
    }

    assert tuple(pairs(query_set_mock, 0, 3)) == (
        (item0, item1),
        (item0, item2),
        (item1, item2),
    )
