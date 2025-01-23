from itertools import batched
from typing import Any, Mapping

import celery
from celery import canvas

from hope_dedup_engine.config.celery import app
from hope_dedup_engine.utils.celery.task_result import wrapped

SerializedTask = dict[str, Any]


@app.task(bind=True)
@wrapped
def map_[
    T
](self: celery.Task, results: list[T], serialize_task: SerializedTask) -> list[T]:
    """Celery map/starmap/xmap cannot be used in chain"""
    signature = self.app.signature(serialize_task)
    return list(map(signature, results))


@app.task
@wrapped
def noop(*_: Any, **__: Any) -> None:
    pass


@app.task
@wrapped
def concat_lists[T](items: list[list[T]]) -> list[T]:
    return sum(items, start=[])


NOOP: Mapping = dict(noop.s())


@app.task(bind=True)
@wrapped
def parallelize[
    T
](
    self: celery.Task,
    producer: SerializedTask,
    task: SerializedTask,
    size: int,
    end_task: SerializedTask = NOOP,
) -> list[T]:
    data = self.app.signature(producer)()

    signature: canvas.Signature = self.app.signature(task)

    signatures = []
    for batch in batched(data, size):
        args = (batch,)
        if isinstance(signature, canvas._chain):
            clone = signature.clone()
            # Celery chain does not pass arguments to the first task
            clone.tasks[0].args = args + clone.tasks[0].args
        else:
            clone = signature.clone(args)
        signatures.append(clone)

    chord = celery.chord(signatures, self.app.signature(end_task))

    return self.replace(chord)
