import pytest

from hope_dedup_engine.apps.api.admin.encoding.utils.threshold import group_by_thresholds, calculate_thresholds


def identity(x):
    return x


@pytest.mark.parametrize(
    ("min_threshold", "max_threshold", "expected_thresholds"),
    [
        pytest.param(50, 100, [50, 56, 61, 67, 72, 78, 83, 89, 94, 100], id="default"),
        pytest.param(95, 100, [95, 96, 97, 98, 99, 100], id="small interval"),
    ],
)
def test_calculate_thresholds(min_threshold: int, max_threshold: int, expected_thresholds: list[int]) -> None:
    assert calculate_thresholds(min_threshold, max_threshold) == expected_thresholds


def test_group_by_thresholds_all_buckets_have_values() -> None:
    thresholds = [3, 6, 9]
    values = range(10)
    assert group_by_thresholds(thresholds, values, identity) == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


def test_group_by_thresholds_all_buckets_are_empty() -> None:
    thresholds = [3, 6, 9]
    values = []
    assert group_by_thresholds(thresholds, values, identity) == [[], [], [], []]
