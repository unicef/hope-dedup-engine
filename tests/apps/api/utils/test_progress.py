from unittest.mock import Mock

import pytest

from hope_dedup_engine.apps.api.utils.progress import (
    STEP,
    callback_filter,
    track_progress,
    track_progress_multi,
)


@pytest.mark.parametrize(
    ("progress_sequence", "step", "expected_calls"),
    [
        ([0, 1, 5, 9, 10, 11, 19, 20, 21], 10, [0, 10, 20]),
        ([0, 1, 4, 5, 6, 9, 10], 5, [0, 5, 10]),
        ([99, 100], 10, [90, 100]),
    ],
)
def test_callback_filter(progress_sequence, step, expected_calls):
    """Test that callback_filter calls the callback only on step boundaries."""
    mock_callback = Mock()
    update = callback_filter(mock_callback, step)

    for progress in progress_sequence:
        update(progress)

    assert mock_callback.call_count == len(expected_calls)
    mock_callback.assert_has_calls([((call,),) for call in expected_calls])


@pytest.mark.parametrize("send_zero", [True, False])
def test_track_progress_send_zero(send_zero):
    """Test track_progress with and without send_zero."""
    mock_callback = Mock()
    update = track_progress(mock_callback, send_zero=send_zero)

    if send_zero:
        mock_callback.assert_called_once_with(0)
    else:
        mock_callback.assert_not_called()

    mock_callback.reset_mock()

    update(5)
    if send_zero:
        mock_callback.assert_not_called()
    else:
        mock_callback.assert_called_once_with(0)
        mock_callback.reset_mock()

    update(9)
    mock_callback.assert_not_called()

    update(10)
    mock_callback.assert_called_once_with(10)


def test_track_progress_default_step():
    """Test track_progress uses the default STEP."""
    mock_callback = Mock()
    update = track_progress(mock_callback, send_zero=False)

    for i in range(STEP):
        update(i)
    mock_callback.assert_called_once_with(0)
    mock_callback.reset_mock()

    for i in range(STEP):
        update(i)
    mock_callback.assert_not_called()

    update(STEP)
    mock_callback.assert_called_once_with(STEP)


def test_track_progress_multi_single_tracker():
    """Test track_progress_multi with a single progress tracker."""
    mock_callback = Mock()
    tracker_gen = track_progress_multi(mock_callback)

    update1 = next(tracker_gen)

    mock_callback.assert_called_once_with(0)
    mock_callback.reset_mock()

    update1(50)
    mock_callback.assert_called_once_with(50)
    mock_callback.reset_mock()

    update1(100)
    mock_callback.assert_called_once_with(100)


def test_track_progress_multi_multiple_trackers():
    """Test track_progress_multi with multiple trackers, checking averaging."""
    mock_callback = Mock()
    tracker_gen = track_progress_multi(mock_callback)

    update1 = next(tracker_gen)
    mock_callback.assert_called_once_with(0)
    mock_callback.reset_mock()

    update2 = next(tracker_gen)
    mock_callback.assert_not_called()

    update1(50)
    mock_callback.assert_called_once_with(20)
    mock_callback.reset_mock()

    update2(50)
    mock_callback.assert_called_once_with(50)
    mock_callback.reset_mock()

    update1(100)
    mock_callback.assert_called_once_with(70)
    mock_callback.reset_mock()

    update2(100)
    mock_callback.assert_called_once_with(100)
    mock_callback.reset_mock()

    update1(101)
    # avg(101, 100) = 100.5 -> 100. Same as before, so no call.
    mock_callback.assert_not_called()

    # Test that decreasing progress doesn't trigger a callback
    update1(50)
    # avg(50, 100) = 75 -> 70. `previous_callback_value` is 100, so no call.
    mock_callback.assert_not_called()


def test_track_progress_multi_many_trackers():
    """Test track_progress_multi with three trackers."""
    mock_callback = Mock()
    tracker_gen = track_progress_multi(mock_callback)

    update1 = next(tracker_gen)
    update2 = next(tracker_gen)
    update3 = next(tracker_gen)

    mock_callback.assert_called_once_with(0)
    mock_callback.reset_mock()

    update1(100)
    mock_callback.assert_called_once_with(30)
    mock_callback.reset_mock()

    update2(100)
    mock_callback.assert_called_once_with(60)
    mock_callback.reset_mock()

    update3(100)
    mock_callback.assert_called_once_with(100)
