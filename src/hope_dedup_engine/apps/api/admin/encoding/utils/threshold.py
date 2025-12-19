from typing import Iterable, Callable, Any

NUMBER_OF_THRESHOLD_VALUES = 10


def calculate_thresholds(min_threshold: int, max_threshold: int) -> list[int]:
    step = (max_threshold - min_threshold) / (NUMBER_OF_THRESHOLD_VALUES - 1)
    thresholds = [min_threshold + step * i for i in range(NUMBER_OF_THRESHOLD_VALUES)]
    thresholds[-1] = max_threshold
    return sorted(set(map(round, thresholds)))


def group_by_thresholds(
    thresholds: Iterable[float], values: Iterable[Any], key: Callable[[Any], float]
) -> list[list[Any]]:
    sorted_values = sorted(values, key=key)
    sorted_thresholds = sorted(thresholds)

    bins = []
    start = 0
    for threshold in sorted_thresholds:
        bin_ = []
        for i in range(start, len(sorted_values)):
            if key(sorted_values[i]) >= threshold:
                break
            bin_.append(sorted_values[i])
        bins.append(bin_)
        start += len(bin_)

    bins.append(sorted_values[start:])

    return bins
