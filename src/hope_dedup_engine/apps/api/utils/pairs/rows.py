from collections.abc import Generator

from hope_dedup_engine.apps.api.utils.pairs.row import (
    Row,
    adjust_end as adjust_row_end,
    adjust_start as adjust_row_start,
    count_pairs,
    pairs as row_pairs,
    row_for,
    row_at,
)


def adjust_start(rows: list[Row], start: int) -> None:
    if len(rows) > 0:
        rows[0] = adjust_row_start(rows[0], start - count_pairs(rows[0].index - 1))


def adjust_end(rows: list[Row], end: int) -> None:
    if len(rows) > 0:
        rows[-1] = adjust_row_end(rows[-1], end - count_pairs(rows[-1].index - 1))


def rows_from_pair_range(start: int, end: int) -> tuple[Row, ...]:
    first_index = row_for(pair_index=start)
    last_index = row_for(pair_index=end)

    rows = [row_at(index=index) for index in range(first_index, last_index + 1)]
    adjust_start(rows, start)
    adjust_end(rows, end)

    return tuple(rows)


def pairs(rows: tuple[Row, ...]) -> Generator[tuple[int, int]]:
    for row in rows:
        yield from row_pairs(row)
