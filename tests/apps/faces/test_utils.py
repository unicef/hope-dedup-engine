import pytest

from hope_dedup_engine.apps.api.models import Image
from hope_dedup_engine.apps.faces.utils import is_facial_error


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Image.StatusCode.DEDUPLICATE_SUCCESS, False),
        (Image.StatusCode.DEDUPLICATE_SUCCESS.name, False),
        (Image.StatusCode.DEDUPLICATE_SUCCESS.label, False),
        (200, False),
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
