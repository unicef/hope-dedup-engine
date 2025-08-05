import json

import pytest
from django_svelte_jsoneditor.widgets import SvelteJSONEditorWidget

from hope_dedup_engine.apps.api.forms import EditSchemaForm


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("form_data", "should_be_valid", "expected_cleaned_data"),
    [
        ({"schema": json.dumps({"key": "value"})}, True, {"key": "value"}),
        ({"schema": '{"key": "value"'}, False, None),
        ({"schema": "just a string"}, False, None),
        ({}, False, None),
    ],
)
def test_form_validation(form_data, should_be_valid, expected_cleaned_data):
    """Test EditSchemaForm with various data, including cleaned_data."""
    form = EditSchemaForm(data=form_data)
    assert form.is_valid() is should_be_valid
    if should_be_valid:
        assert form.cleaned_data["schema"] == expected_cleaned_data
    else:
        assert "schema" in form.errors


@pytest.mark.django_db
def test_form_widget():
    """Test form uses the correct widget for the 'schema' field."""
    form = EditSchemaForm()
    assert isinstance(form.fields["schema"].widget, SvelteJSONEditorWidget)
