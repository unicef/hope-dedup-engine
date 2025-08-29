import pytest
from pytest_mock import MockerFixture

from hope_dedup_engine.config.utils import (
    get_core_count,
    get_number_of_disks,
    ASSUMED_DISK_COUNT,
    get_pool_config,
    PoolConfig,
    clamp,
    MIN_POOL_SIZE,
    MAX_MIN_POOL_SIZE,
    MAX_POOL_SIZE,
    MIN_GREATER_THAN_MAX_ERROR,
)


MIN_VALUE = 5
VALUE = 10
MAX_VALUE = 15


@pytest.mark.parametrize(
    ("value", "min_value", "max_value", "expected_result"),
    [
        (VALUE, MIN_VALUE, MAX_VALUE, VALUE),
        (MIN_VALUE, MIN_VALUE, MAX_VALUE, MIN_VALUE),
        (MAX_VALUE, MIN_VALUE, MAX_VALUE, MAX_VALUE),
        (MIN_VALUE - 1, MIN_VALUE, MAX_VALUE, MIN_VALUE),
        (MAX_VALUE + 1, MIN_VALUE, MAX_VALUE, MAX_VALUE),
        (MIN_VALUE, VALUE, VALUE, VALUE),
        (MAX_VALUE, VALUE, VALUE, VALUE),
    ],
)
def test_clamp(value: int, min_value: int, max_value: int, expected_result: int) -> None:
    assert clamp(value, min_value, max_value) == expected_result


def test_clamp_rises_error_when_min_greater_than_max() -> None:
    with pytest.raises(ValueError, match=MIN_GREATER_THAN_MAX_ERROR):
        clamp(VALUE, MAX_VALUE, MIN_VALUE)


@pytest.mark.parametrize(("sched_getaffinity_return", "expected_result"), [(set(), 0), ({0}, 1), ({0, 1}, 2)])
def test_get_core_count(mocker: MockerFixture, sched_getaffinity_return: set[int], expected_result: int) -> None:
    sched_getaffinity_mock = mocker.patch(
        "hope_dedup_engine.config.utils.os.sched_getaffinity", return_value=sched_getaffinity_return
    )
    assert get_core_count() == expected_result
    sched_getaffinity_mock.assert_called_once_with(0)


@pytest.mark.parametrize(("cpu_count_return", "expected_result"), [(0, 0), (1, 1), (2, 2)])
def test_get_core_count_sched_getaffinity_not_available(
    mocker: MockerFixture, cpu_count_return: int, expected_result: int
) -> None:
    sched_getaffinity_mock = mocker.patch(
        "hope_dedup_engine.config.utils.os.sched_getaffinity", side_effect=AttributeError
    )
    cpu_count_mock = mocker.patch("hope_dedup_engine.config.utils.os.cpu_count", return_value=cpu_count_return)

    assert get_core_count() == expected_result
    sched_getaffinity_mock.assert_called_once_with(0)
    cpu_count_mock.assert_called_once_with()


def test_get_number_of_disks() -> None:
    assert get_number_of_disks() == ASSUMED_DISK_COUNT


def test_get_pool_config(mocker: MockerFixture) -> None:
    core_count = 2
    disk_count = 1

    get_core_count_mock = mocker.patch("hope_dedup_engine.config.utils.get_core_count", return_value=core_count)
    get_number_of_disks_mock = mocker.patch(
        "hope_dedup_engine.config.utils.get_number_of_disks", return_value=disk_count
    )
    clamp_mock = mocker.patch("hope_dedup_engine.config.utils.clamp")
    optimal_pool_size = core_count * 2 + disk_count
    max_pool_size = max(optimal_pool_size, MAX_POOL_SIZE)

    assert get_pool_config() == PoolConfig(
        min_size=clamp_mock.return_value, max_size=clamp_mock.return_value, max_idle=4.0 * 60
    )
    get_core_count_mock.assert_called_once_with()
    get_number_of_disks_mock.assert_called_once_with()
    clamp_mock.assert_has_calls(
        [
            mocker.call(max_pool_size // 2, MIN_POOL_SIZE, MAX_MIN_POOL_SIZE),
            mocker.call(max_pool_size, MIN_POOL_SIZE, MAX_POOL_SIZE),
        ]
    )
