from django.forms import ValidationError

import pytest

from hope_dedup_engine.apps.faces.validators import MeanValuesTupleField


def test_to_python_valid_tuple():
    field = MeanValuesTupleField()
    assert field.to_python("104.0, 177.0, 123.0") == (104.0, 177.0, 123.0)


def test_to_python_invalid_length():
    field = MeanValuesTupleField()
    with pytest.raises(ValidationError) as exc_info:
        field.to_python("104.0, 177.0")
    assert "Enter a valid tuple of three float values separated by commas and spaces" in str(exc_info.value)


def test_to_python_value_out_of_range():
    field = MeanValuesTupleField()
    with pytest.raises(ValidationError) as exc_info:
        field.to_python("104.0, 177.0, 256.0")
    assert "Each value must be between -255 and 255." in str(exc_info.value)


def test_to_python_non_numeric_value():
    field = MeanValuesTupleField()
    with pytest.raises(ValidationError) as exc_info:
        field.to_python("104.0, abc, 123.0")
    assert "Enter a valid tuple of three float values separated by commas and spaces" in str(exc_info.value)


def test_prepare_value_with_tuple():
    field = MeanValuesTupleField()
    assert field.prepare_value((104.0, 177.0, 123.0)) == "104.0, 177.0, 123.0"


def test_prepare_value_with_string():
    field = MeanValuesTupleField()
    assert field.prepare_value("104.0, 177.0, 123.0") == "104.0, 177.0, 123.0"
