from collections.abc import Collection, Generator
from functools import partial
from itertools import accumulate, islice, takewhile
from operator import ge

type CompactPairs[T] = tuple[Collection[T], int, int]


def total_length(collection: Collection) -> int:
    return (collection_length := len(collection)) * (collection_length - 1) // 2


def length(compact_pairs: CompactPairs) -> int:
    sequence, start, stop = compact_pairs
    return stop - start if stop else total_length(sequence) - start


def from_collection[T](collection: Collection[T]) -> CompactPairs[T]:
    return collection, 0, total_length(collection)


def optimize[T](compact_pairs: CompactPairs[T]) -> CompactPairs[T]:
    sequence, start, end = compact_pairs
    deltas = tuple(
        takewhile(partial(ge, start), accumulate(range(len(sequence) - 1, 0, -1)))
    )
    skip = len(deltas)
    sequence = sequence[skip:]
    if deltas:
        start -= deltas[-1]
        if end:
            end -= deltas[-1]

    return sequence, start, end


def unwrap[T](pairs: CompactPairs[T]) -> Generator[tuple[T, T], None, None]:
    sequence, start, end = pairs
    all_pairs = (
        (e1, e2) for i, e1 in enumerate(sequence) for e2 in sequence[i + 1:]  # fmt: skip
    )
    yield from islice(all_pairs, start, end)


def split[
    T
](pairs: CompactPairs[T], size: int) -> Generator[CompactPairs[T], None, None]:
    sequence, start, stop = pairs
    stop = stop or length(pairs)
    bounds = list(range(start, stop + 1, size))
    if bounds[-1] < stop:
        bounds.append(stop)

    for start, stop in zip(bounds, bounds[1:]):
        yield optimize((sequence, start, stop))
