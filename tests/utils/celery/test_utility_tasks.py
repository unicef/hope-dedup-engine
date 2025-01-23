from itertools import batched
from unittest.mock import MagicMock, call

import celery
from celery import canvas
from pytest import mark
from pytest_mock import MockerFixture

from hope_dedup_engine.utils.celery.task_result import make_value
from hope_dedup_engine.utils.celery.utility_tasks import concat_lists, map_, parallelize


def test_concat_lists() -> None:
    data = list(range(10))
    batched_data = list(map(list, batched(data, 5)))
    assert concat_lists(batched_data) == make_value(data)


def test_map_() -> None:
    data = list(range(10))
    task = MagicMock(spec=celery.Task)
    serialized_signature = MagicMock()
    signature = task.app.signature.return_value

    # we have to skip task binding
    map_.__wrapped__.__func__(task, data, serialized_signature)

    signature.assert_has_calls([call(i) for i in data])
    assert signature.call_count == len(data)


@mark.parametrize("signature", (MagicMock(), MagicMock(spec=canvas._chain)))
def test_parallelize(mocker: MockerFixture, signature: MagicMock) -> None:
    data = list(range(10))
    batch_size = 5
    batched_data = list(map(tuple, batched(data, batch_size)))
    task = MagicMock(spec=celery.Task)
    serialized_signature = MagicMock()
    task.app.signature.return_value = signature
    chord_mock = mocker.patch(
        "hope_dedup_engine.utils.celery.utility_tasks.celery.chord"
    )
    concat_mock = mocker.patch("hope_dedup_engine.utils.celery.utility_tasks.concat")

    parallelize.__wrapped__.__func__(task, data, serialized_signature, batch_size)

    chord_mock.assert_called_once_with(
        [signature.clone.return_value] * len(batched_data), concat_mock.s.return_value
    )
    task.replace.assert_called_once_with(chord_mock.return_value)
