import multiprocessing
import os
from typing import TypedDict

# just an assumption
ASSUMED_DISK_COUNT = 1


class PoolConfig(TypedDict):
    min_size: int
    max_size: int
    max_idle: float


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


def get_pool_config() -> PoolConfig:
    # A commonly used formula to estimate pool size: (2 * core_count) + number_of_disks
    # on k8s get_core_count can return 0 if no limits are set, so we use max(get_core_count(), 1)
    max_connections = 2 * max(get_core_count(), 1) + get_number_of_disks()
    min_connections = max_connections // 2

    return {
        "min_size": max(min_connections, 1),
        "max_size": max(max_connections, 1),
        # we don't need max_size connections all the time, and if connections
        # are not heavily used, we can start shrinking the pool
        "max_idle": 0.5 * 60,
    }
