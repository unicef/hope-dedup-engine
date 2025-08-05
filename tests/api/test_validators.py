import pytest
from constance.test import override_config

from hope_dedup_engine.apps.api.validators import DefaultValidatingValidator


@pytest.mark.api
def test_validator():
    """Test that default values are set on the instance."""
    schema = {
        "type": "object",
        "properties": {
            "foo": {"type": "number", "default": 42},
            "bar": {"type": "string"},
            "baz": {"type": "string", "default": "hello"},
        },
    }
    instance = {"bar": "world"}
    validator = DefaultValidatingValidator(schema)
    validator.validate(instance)
    assert instance == {"bar": "world", "foo": 42, "baz": "hello"}


@pytest.mark.api
@override_config(FACE_RECOGNITION_MODEL="test_model")
def test_default_constance():
    """Test that default values from constance config are set."""
    schema = {
        "type": "object",
        "properties": {
            "foo": {"type": "string", "default": "constance.config.FACE_RECOGNITION_MODEL"},
        },
    }
    instance = {}
    validator = DefaultValidatingValidator(schema)
    validator.validate(instance)
    assert instance == {"foo": "test_model"}


@pytest.mark.api
def test_constance_not_set():
    """Test that default is None when constance config is not set."""
    schema = {
        "type": "object",
        "properties": {
            "foo": {"type": ["string", "null"], "default": "constance.config.NON_EXISTENT"},
        },
    }
    instance = {}
    validator = DefaultValidatingValidator(schema)
    validator.validate(instance)
    assert instance == {"foo": None}
