from itertools import batched
from typing import Any, NoReturn

import celery
from celery import canvas

from hope_dedup_engine.config.celery import app
from hope_dedup_engine.utils.celery.task_result import unwrap_result, wrapped

SerializedTask = dict[str, Any]


@app.task(bind=True)
@wrapped
def parallelize(
    self: celery.Task,
    producer: SerializedTask,
    task: SerializedTask,
    batch_size: int,
    end_task: SerializedTask | None = None,
) -> NoReturn:
    producer_signature = self.app.signature(producer)
    data = unwrap_result(producer_signature())

    signature: canvas.Signature = self.app.signature(task)

    signatures = []
    for batch in batched(data, batch_size):
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
