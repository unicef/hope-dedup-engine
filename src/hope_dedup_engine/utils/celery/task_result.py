import json
from collections.abc import Callable
from functools import wraps
from typing import Any, Literal, NotRequired, TypedDict

import celery
from celery import exceptions as celery_exceptions
from celery import signals as celery_signals
from celery.states import FAILURE
from django_celery_results.models import TaskResult

# Because of few bugs in Celery it cannot handle exceptions in chains,
# groups, and chords if those structures are nested. An exception can make
# entire pipeline stuck in the PENDING state. That is why we cannot allow tasks
# to throw exceptions and have to pass both result and error in the same data
# structure.

DATA: Literal["data"] = "data"
IS_WRAPPED: Literal["is_wrapped"] = "is_wrapped"
MESSAGE: Literal["message"] = "message"
UNKNOWN_RESULT: Literal["Unknown result"] = "Unknown result"
PROPAGATED: Literal["propagated"] = "propagated"


# Because of Celery default JSON serializer we cannot use classes or dataclasses
# to represent a result
class Result(TypedDict):
    is_wrapped: bool


class Value(Result):
    data: Any


class Error(Result):
    message: str
    propagated: NotRequired[bool]


class UnexpectedResultError(Exception):
    def __init__(self, result: Result, container: Any | None = None) -> None:
        message = (
            f"{UNKNOWN_RESULT}: {result}"
            if container is None
            else f"{UNKNOWN_RESULT}: {result} in {container}"
        )
        super().__init__(message)


def is_result(a: Any) -> bool:
    return isinstance(a, dict) and a.get(IS_WRAPPED) is True


def is_value(a: Any) -> bool:
    return is_result(a) and DATA in a


def is_error(a: Any) -> bool:
    return is_result(a) and MESSAGE in a


def mark_propagated(error: Error) -> None:
    error[PROPAGATED] = True


def make_value(v: Any) -> Value:
    return {IS_WRAPPED: True, DATA: v}


def make_error(e: Exception) -> Error:
    name = e.__class__.__name__
    args = ", ".join(map(str, e.args))
    return {IS_WRAPPED: True, MESSAGE: f"{name}: {args}"}


def is_result_list(a: Any) -> bool:
    return isinstance(a, list) and any(map(is_result, a))


def result_list_to_list_result(results: list[Any]) -> Result:
    if error := next(filter(is_error, results), None):
        return error

    output = []
    for result in results:
        if is_result(result):
            if not is_value(result):
                return make_error(UnexpectedResultError(result, results))

            output.append(result[DATA])
        else:
            output.append(result)

    return make_value(output)


def handle_result_list(value: Any) -> Any:
    return result_list_to_list_result(value) if is_result_list(value) else value


def wrapped(f: Callable) -> Callable:
    @wraps(f)
    def inner(*args: Any, **kwargs: Any) -> Result:
        self = None
        if args and isinstance(args[0], celery.Task):
            self = args[0]
            args = args[1:]

        if args:
            first_arg = handle_result_list(args[0])  # Celery group result
            if is_result(first_arg):
                if is_error(first_arg):
                    mark_propagated(first_arg)
                    return first_arg

                if is_value(first_arg):
                    args = (first_arg[DATA],) + args[1:]
                else:
                    return make_error(UnexpectedResultError(first_arg))

        try:
            if self:
                args = (self,) + args

            result = f(*args, **kwargs)

            # wrapping result task was mapped over sequence
            if is_result_list(result):
                return result_list_to_list_result(result)

            return make_value(result)
        except celery_exceptions.Ignore:
            raise
        except Exception as e:
            return make_error(e)

    return inner


def unwrap_result(result: Any) -> Any:
    if not is_result(result):
        return result

    if is_value(result):
        return result[DATA]
    elif is_error(result):
        raise Exception(MESSAGE)

    raise UnexpectedResultError(result)


@celery_signals.task_postrun.connect
def fix_results_in_db(sender=None, headers=None, body=None, **kwargs) -> None:
    if (task_id := kwargs.get("task_id")) and (result := kwargs.get("retval")):
        if is_result(result):
            result_model = TaskResult.objects.get(task_id=task_id)
            if is_value(result):
                result_model.result = json.dumps(result[DATA])
            elif is_error(result):
                if result.get(PROPAGATED):
                    result_model.delete()
                else:
                    result_model.result = result[MESSAGE]
                    result_model.status = FAILURE
                    result_model.save()
