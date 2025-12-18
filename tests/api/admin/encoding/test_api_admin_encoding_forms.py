import pytest

from hope_dedup_engine.apps.api.admin.encoding.forms import DeduplicateForm, FindFaceForm


@pytest.mark.parametrize(
    ("data", "is_valid"),
    [
        pytest.param({"min_threshold": 50, "max_threshold": 100}, True, id="valid case"),
        pytest.param({"min_threshold": 99, "max_threshold": 51}, False, id="max_threshold < min_threshold"),
    ],
)
def test_find_face_form(data: dict[str, int], is_valid: bool) -> None:
    form = FindFaceForm(data=data)
    assert form.is_valid() is is_valid


@pytest.mark.parametrize(
    ("data", "is_valid"),
    [
        pytest.param({"min_threshold": 50, "max_threshold": 100}, True, id="valid case"),
        pytest.param({"min_threshold": 99, "max_threshold": 51}, False, id="max_threshold < min_threshold"),
    ],
)
def test_deduplicate_form_default(data: dict[str, int], is_valid: bool) -> None:
    form = DeduplicateForm(data={"action": "action", "_selected_action": "selected_action", **data})
    assert form.is_valid() is is_valid
