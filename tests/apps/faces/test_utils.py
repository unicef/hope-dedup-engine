from unittest.mock import patch

import pytest

from hope_dedup_engine.apps.api.models import Image
from hope_dedup_engine.apps.faces.utils import is_facial_error, report_long_execution


@pytest.mark.parametrize(
    ("time_side_effect", "should_be_called"),
    [
        ([0, 1], False),  # 1 second duration, less than threshold
        ([0, 6], True),  # 6 seconds duration, more than threshold
    ],
)
@patch("hope_dedup_engine.apps.faces.utils.sentry_sdk")
def test_report_long_execution(mock_sentry, time_side_effect, should_be_called, settings):
    """Test that `report_long_execution` only sends a message to Sentry for long executions."""
    settings.DEFAULT_THRESHOLD_SECONDS = 5
    with patch("time.time", side_effect=time_side_effect):
        with report_long_execution("Test Task"):
            pass  # Simulate some work

    if should_be_called:
        mock_sentry.capture_message.assert_called_once()
        message = mock_sentry.capture_message.call_args.args[0]
        assert "Execution took" in message
        assert "seconds: Test Task" in message
    else:
        mock_sentry.capture_message.assert_not_called()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Success cases (not errors)
        (Image.StatusCode.DEDUPLICATE_SUCCESS, False),
        (Image.StatusCode.DEDUPLICATE_SUCCESS.name, False),
        (Image.StatusCode.DEDUPLICATE_SUCCESS.label, False),
        (200, False),
        # Error cases
        (Image.StatusCode.NO_FILE_FOUND, True),
        (Image.StatusCode.NO_FILE_FOUND.name, True),
        (Image.StatusCode.NO_FILE_FOUND.label, True),
        (404, True),
        (Image.StatusCode.NO_FACE_DETECTED, True),
        (412, True),
        (Image.StatusCode.MULTIPLE_FACES_DETECTED, True),
        (429, True),
        (Image.StatusCode.GENERIC_ERROR, True),
        (500, True),
        # Invalid values
        ("some_random_string", False),
        (999, False),
        (None, False),
        ([], False),
        ({}, False),
    ],
)
def test_is_facial_error(value, expected):
    """Test `is_facial_error` correctly identifies facial processing errors."""
    assert is_facial_error(value) == expected
