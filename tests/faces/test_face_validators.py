import pytest
from django.core.exceptions import ValidationError

from hope_dedup_engine.apps.faces.validators import IgnorePairsValidator


@pytest.mark.parametrize(
    "empty_input",
    [
        None,
        [],
    ],
)
def test_validate_empty_ignore(empty_input):
    assert IgnorePairsValidator.validate(empty_input) == set()


def test_validate_valid_ignore():
    ignore = [["a", "b"], ["c", "d"]]
    expected = {("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")}
    assert IgnorePairsValidator.validate(ignore) == expected


@pytest.mark.parametrize(
    "invalid_input",
    [
        ("a", "b"),
        [("a", "b")],
        [["a", "b", "c"]],
        [["a", 1]],
        [["a", ""]],
    ],
)
def test_validate_invalid_format(invalid_input):
    with pytest.raises(ValidationError, match="Invalid format for ignore pairs."):
        IgnorePairsValidator.validate(invalid_input)
