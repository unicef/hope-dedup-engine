from hope_dedup_engine.apps.api.admin.encoding.utils.threshold import group_by_thresholds


def identity(x):
    return x


def test_all_buckets_have_values() -> None:
    thresholds = [3, 6, 9]
    values = range(10)
    assert group_by_thresholds(thresholds, values, identity) == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


def test_all_buckets_are_empty() -> None:
    thresholds = [3, 6, 9]
    values = []
    assert group_by_thresholds(thresholds, values, identity) == [[], [], [], []]
