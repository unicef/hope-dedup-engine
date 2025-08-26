import pytest
from pytest_mock import MockerFixture

from hope_dedup_engine.config.utils import (
    get_core_count,
    get_number_of_disks,
    ASSUMED_DISK_COUNT,
    get_pool_config,
    PoolConfig,
)


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


@pytest.mark.parametrize(
    ("get_core_count_return", "get_number_of_disks_return", "expected_result"),
    [
        (0, 0, PoolConfig(min_size=1, max_size=1, max_idle=0.5 * 60)),
        (0, 1, PoolConfig(min_size=1, max_size=1, max_idle=0.5 * 60)),
        (1, 0, PoolConfig(min_size=1, max_size=2, max_idle=0.5 * 60)),
        (1, 1, PoolConfig(min_size=1, max_size=3, max_idle=0.5 * 60)),
        (2, 2, PoolConfig(min_size=3, max_size=6, max_idle=0.5 * 60)),
    ],
)
def test_get_pool_config(
    mocker: MockerFixture, get_core_count_return: int, get_number_of_disks_return: int, expected_result: PoolConfig
) -> None:
    get_core_count_mock = mocker.patch(
        "hope_dedup_engine.config.utils.get_core_count", return_value=get_core_count_return
    )
    get_number_of_disks_mock = mocker.patch(
        "hope_dedup_engine.config.utils.get_number_of_disks", return_value=get_number_of_disks_return
    )

    assert get_pool_config() == expected_result
    get_core_count_mock.assert_called_once_with()
    get_number_of_disks_mock.assert_called_once_with()
