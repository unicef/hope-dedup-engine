import multiprocessing
import os
from typing import TypedDict

ASSUMED_DISK_COUNT = 1


class PoolConfig(TypedDict):
    min_size: int
    max_size: int
    max_idle: float


MIN_GREATER_THAN_MAX_ERROR = "min_value must be greater than max_value"


def clamp(value: int, min_value: int, max_value: int) -> int:
    if min_value > max_value:
        raise ValueError(MIN_GREATER_THAN_MAX_ERROR)

    return max(min(value, max_value), min_value)


def get_core_count() -> int:
    # TODO: when upgraded to Python 3.13 use os.process_cpu_count() instead of
    #       len(os.sched_getaffinity(0)) as it's cross platform
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        # not-so-good alternative as not all cores can be available for usage
        return multiprocessing.cpu_count()


def get_number_of_disks() -> int:
    return ASSUMED_DISK_COUNT


MIN_POOL_SIZE = 3
MAX_POOL_SIZE = 100
MAX_MIN_POOL_SIZE = MAX_POOL_SIZE // 2


def get_pool_config() -> PoolConfig:
    # A commonly used formula to estimate pool size: (2 * core_count) + number_of_disks
    # on k8s get_core_count can return 0 if no limits are set, so we use max(get_core_count(), 1)
    optimal_number_of_connections = 2 * max(get_core_count(), 1) + get_number_of_disks()

    max_connections = max(optimal_number_of_connections, MAX_POOL_SIZE)
    min_connections = max_connections // 2

    return {
        "min_size": clamp(min_connections, MIN_POOL_SIZE, MAX_MIN_POOL_SIZE),
        "max_size": clamp(max_connections, MIN_POOL_SIZE, MAX_POOL_SIZE),
        "max_idle": 4.0 * 60,
    }
