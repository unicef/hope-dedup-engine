from collections.abc import Callable
from unittest.mock import MagicMock

import celery
from celery.exceptions import Ignore
from pytest import fixture, raises

from hope_dedup_engine.utils.celery.task_result import (
    DATA,
    IS_WRAPPED,
    MESSAGE,
    UnexpectedResultError,
    make_error,
    make_value,
    wrapped,
)

VALUE = {IS_WRAPPED: True, DATA: 42}
ERROR = {IS_WRAPPED: True, MESSAGE: "Oops"}
UNKNOWN = {IS_WRAPPED: True}


@fixture
def function() -> MagicMock:
    return MagicMock()


@fixture
def wrapped_function(function: MagicMock) -> Callable:
    return wrapped(function)


def test_function_is_called_with_unwrapped_data(
    function: MagicMock, wrapped_function: Callable
) -> None:
    wrapped_function(VALUE)
    function.assert_called_once_with(VALUE[DATA])


def test_non_wrapped_value_passed_as_is(
    function: MagicMock, wrapped_function: Callable
) -> None:
    wrapped_function(VALUE[DATA])
    function.assert_called_once_with(VALUE[DATA])


def test_error_is_propagated(function: MagicMock, wrapped_function: Callable) -> None:
    result = wrapped_function(ERROR)
    assert result is ERROR
    function.assert_not_called()


def test_exception_is_wrapped(function: MagicMock, wrapped_function: Callable) -> None:
    exception = Exception("Test")
    function.side_effect = exception
    assert wrapped_function() == make_error(exception)


def test_ignore_exception_is_propagated(
    function: MagicMock, wrapped_function: Callable
) -> None:
    function.side_effect = Ignore()
    with raises(Ignore):
        wrapped_function()


def test_unknown_result_type_results_in_error(
    function: MagicMock, wrapped_function: Callable
) -> None:
    assert wrapped_function(UNKNOWN) == make_error(UnexpectedResultError(UNKNOWN))


def test_task_is_passed(function: MagicMock, wrapped_function: Callable) -> None:
    task = MagicMock(spec=celery.Task)
    wrapped_function(task)
    function.assert_called_once_with(task)


def test_input_list_of_results_is_unwrapped(
    function: MagicMock, wrapped_function: Callable
) -> None:
    wrapped_function([VALUE])
    function.assert_called_once_with([VALUE[DATA]])


def test_error_in_list_is_propagated(
    function: MagicMock, wrapped_function: Callable
) -> None:
    result = wrapped_function([ERROR])
    assert result is ERROR
    function.assert_not_called()


def test_unknown_result_type_in_list_results_in_error(
    function: MagicMock, wrapped_function: Callable
) -> None:
    assert wrapped_function([UNKNOWN]) == make_error(
        UnexpectedResultError(UNKNOWN, [UNKNOWN])
    )


def test_wrapped_and_non_wrapped_values_in_list_passed_correctly(
    function: MagicMock, wrapped_function: Callable
) -> None:
    wrapped_function([VALUE, VALUE[DATA]])
    function.assert_called_once_with([VALUE[DATA], VALUE[DATA]])


def test_output_list_of_results_is_unwrapped(
    function: MagicMock, wrapped_function: Callable
) -> None:
    function.return_value = [VALUE]
    result = wrapped_function()
    assert result == make_value([VALUE[DATA]])
