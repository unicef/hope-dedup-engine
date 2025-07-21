from collections.abc import Callable, Generator
from functools import partial

STEP = 10


def callback_filter(callback: Callable[[int], None], step: int) -> Callable[[int], None]:
    previous_callback_value = -1

    def update(progress: int) -> None:
        nonlocal previous_callback_value
        if (callback_value := progress // step * step) != previous_callback_value:
            callback(callback_value)
            previous_callback_value = callback_value

    return update


def track_progress(callback: Callable[[int], None], send_zero: bool = True) -> Callable[[int], None]:
    update = callback_filter(callback, STEP)

    if send_zero:
        update(0)

    return update


def track_progress_multi(
    callback: Callable[[int], None],
) -> Generator[Callable[[int], None]]:
    progress = []

    update = callback_filter(callback, STEP)

    def individual_callback(value: int, index: int) -> None:
        progress[index] = value
        update(sum(progress) // len(progress))

    send_zero = True
    while True:
        progress.append(0)
        yield track_progress(
            callback=partial(individual_callback, index=len(progress) - 1),
            send_zero=send_zero,
        )
        send_zero = False
