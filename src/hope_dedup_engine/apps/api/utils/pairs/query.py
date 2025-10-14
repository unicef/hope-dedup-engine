from collections.abc import Generator, Mapping
from itertools import groupby
from typing import cast

from django.db.models import QuerySet, Model

from hope_dedup_engine.apps.api.utils.pairs.row import Row, count_pairs as count_pairs_for_row
from hope_dedup_engine.apps.api.utils.pairs.rows import pairs as pairs_from_rows, rows_from_pair_range


def flatten_indices(rows: tuple[Row, ...]) -> tuple[int | None, ...]:
    index_set = set()
    for row in rows:
        index_set.update(row.first_index)
        index_set.add(row.last_index)

    return tuple(index if index in index_set else None for index in range(min(index_set), max(index_set) + 1))


def is_none(index: int | None) -> bool:
    return index is None


def slices_and_ranges(rows: tuple[Row, ...]) -> Generator[tuple[slice, range]]:
    for should_skip, grouped in groupby(flatten_indices(rows), key=is_none):
        if should_skip:
            continue

        group = cast("tuple[int, ...]", tuple(grouped))
        yield slice(group[0], group[-1] + 1), range(group[0], group[-1] + 1)


def load_models[T: Model](query: QuerySet[T], rows: tuple[Row, ...]) -> Mapping[int, T]:
    return {i: m for s, r in slices_and_ranges(rows) for i, m in zip(r, query[s], strict=False)}


def count_pairs(query: QuerySet[Model]) -> int:
    number_of_records = query.count()
    return count_pairs_for_row(number_of_records - 2)


def calculate_chunks(query: QuerySet[Model], total: int, offset: int, size: int) -> Generator[tuple[int, int]]:
    for start in range(offset, total, size):
        end = min(start + size, total)
        yield start, end


def pairs[T: Model](query: QuerySet[T], start: int, end: int) -> Generator[tuple[T, T]]:
    if not query.ordered:
        raise ValueError("QuerySet must be ordered")

    rows = rows_from_pair_range(start, end)
    model_mapping = load_models(query, rows)

    for first, second in pairs_from_rows(rows):
        yield model_mapping[first], model_mapping[second]
