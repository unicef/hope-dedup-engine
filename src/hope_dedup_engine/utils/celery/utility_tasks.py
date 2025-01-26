import itertools
from collections.abc import Iterable
from typing import Any, Generator, NoReturn

import celery
from celery import canvas

from hope_dedup_engine.config.celery import app
from hope_dedup_engine.utils.celery.task_result import unwrap_result, wrapped
from hope_dedup_engine.utils.compact_pairs import CompactPairs, split

SerializedTask = dict[str, Any]


@app.task
def batched[T](iterable: Iterable[T], size: int) -> Iterable[Iterable[T]]:
    return itertools.batched(iterable, size)


@app.task
def batched_compact_pairs[
    T
](pairs: CompactPairs[T], size: int) -> Generator[CompactPairs[T], None, None]:
    return split(pairs, size)


DEFAULT_SPLITTER = batched.s()


@app.task(bind=True)
@wrapped
def parallelize(
    self: celery.Task,
    producer: SerializedTask,
    task: SerializedTask,
    batch_size: int,
    end_task: SerializedTask | None = None,
    splitter: SerializedTask = DEFAULT_SPLITTER,
) -> NoReturn:
    producer_signature = self.app.signature(producer)
    data = unwrap_result(producer_signature())

    signature: canvas.Signature = self.app.signature(task)

    signatures = []
    splitter_signature = self.app.signature(splitter)
    for batch in splitter_signature(data, batch_size):
        args = (batch,)
        if isinstance(signature, canvas._chain):
            clone = signature.clone()
            # Celery chain does not pass arguments to the first task
            clone.tasks[0].args = args + clone.tasks[0].args
        else:
            clone = signature.clone(args)
        signatures.append(clone)

    group = celery.group(signatures)

    if end_task:
        return self.replace(group | self.app.signature(end_task))

    return self.replace(group)
