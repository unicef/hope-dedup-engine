from django import forms

from django_svelte_jsoneditor.widgets import SvelteJSONEditorWidget


class EditSchemaForm(forms.Form):
    schema = forms.JSONField(widget=SvelteJSONEditorWidget())
