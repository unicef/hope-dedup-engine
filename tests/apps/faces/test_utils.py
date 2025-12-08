from unittest.mock import patch

import pytest

from hope_dedup_engine.apps.api.models import Encoding
from hope_dedup_engine.apps.faces.utils import is_facial_error, report_long_execution


@pytest.mark.parametrize(
    ("time_side_effect", "should_be_called"),
    [
        ([0, 1], False),
        ([0, 6], True),
    ],
)
@patch("hope_dedup_engine.apps.faces.utils.sentry_sdk")
def test_report_long_execution(mock_sentry, time_side_effect, should_be_called, settings):
    """Test that `report_long_execution` only sends a message to Sentry for long executions."""
    settings.DEFAULT_THRESHOLD_SECONDS = 5
    with patch("time.time", side_effect=time_side_effect):
        with report_long_execution("Test Task"):
            pass

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
        (Encoding.StatusCode.DEDUPLICATE_SUCCESS, False),
        (Encoding.StatusCode.DEDUPLICATE_SUCCESS.name, False),
        (Encoding.StatusCode.DEDUPLICATE_SUCCESS.label, False),
        (200, False),
        (Encoding.StatusCode.FILE_NOT_FOUND, True),
        (Encoding.StatusCode.FILE_NOT_FOUND.name, True),
        (Encoding.StatusCode.FILE_NOT_FOUND.label, True),
        (404, True),
        (Encoding.StatusCode.NO_FACE_DETECTED, True),
        (412, True),
        (Encoding.StatusCode.MULTIPLE_FACES_DETECTED, True),
        (429, True),
        (Encoding.StatusCode.GENERIC_ERROR, True),
        (500, True),
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
