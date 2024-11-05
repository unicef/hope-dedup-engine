from django.forms import ValidationError

import pytest

from hope_dedup_engine.apps.faces.forms import MeanValuesTupleField


def test_to_python_valid_case():
    field = MeanValuesTupleField()
    assert field.to_python("104.0, 177.0, 123.0") == (104.0, 177.0, 123.0)


@pytest.mark.parametrize(
    "input_value, expected_error_message",
    [
        (
            "104.0, 177.0",
            "Enter a valid tuple of three float values separated by commas and spaces",
        ),
        ("104.0, 177.0, 256.0", "Each value must be between -255 and 255."),
        (
            "104.0, abc, 123.0",
            "Enter a valid tuple of three float values separated by commas and spaces",
        ),
    ],
)
def test_to_python_invalid_cases(input_value, expected_error_message):
    field = MeanValuesTupleField()
    with pytest.raises(ValidationError) as exc_info:
        field.to_python(input_value)
    assert expected_error_message in str(exc_info.value)


@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        ((104.0, 177.0, 123.0), "104.0, 177.0, 123.0"),
        ("104.0, 177.0, 123.0", "104.0, 177.0, 123.0"),
    ],
)
def test_prepare_value(input_value, expected_output):
    field = MeanValuesTupleField()
    assert field.prepare_value(input_value) == expected_output
