from collections.abc import Generator
from itertools import repeat
from typing import NamedTuple, cast


class Row(NamedTuple):
    index: int
    first_index: range
    last_index: int


def adjust_start(row: Row, start: int) -> Row:
    return Row(row.index, row.first_index[start:], row.last_index)


def adjust_end(row: Row, end: int) -> Row:
    inverted_end = end - len(row.first_index)
    return Row(row.index, row.first_index[:inverted_end], row.last_index)


def count_pairs(index: int) -> int:
    if index < 0:
        return 0
    return (index + 1) * (index + 2) // 2


def pairs(row: Row) -> Generator[tuple[int, int]]:
    yield from zip(row.first_index, repeat(row.last_index))


def row_for(pair_index: int) -> int:
    return cast("int", round((2 * (pair_index + 1)) ** 0.5) - 1)


def row_at(index: int) -> Row:
    return Row(index, range(index + 1), index + 1)
