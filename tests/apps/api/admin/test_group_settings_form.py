import pytest

from hope_dedup_engine.apps.api.admin.forms import DeduplicationSetGroupSettingsForm

VALID_FORM_DATA = {
    "recognition_model": "Facenet512",
    "detector_backend": "retinaface",
    "distance_metric": "cosine",
    "face_detection_confidence_threshold": 0.8,
    "duplicate_confidence_threshold": 0.6,
    "sharpness_threshold": 0.4,
    "dynamic_range_threshold": 0.3,
    "no_head_cover_threshold": 0.5,
    "eyes_open_threshold": 0.6,
    "inter_eye_distance_threshold": 0.7,
    "unified_quality_score_threshold": 0.8,
}


@pytest.mark.django_db
def test_form_populates_initial_from_settings(deduplication_set_group_factory):
    """__init__ sets field initials from instance.settings."""
    group = deduplication_set_group_factory()
    group.settings = {"recognition_model": "ArcFace", "sharpness_threshold": 0.55}
    group.save()

    form = DeduplicationSetGroupSettingsForm(instance=group)

    assert form.fields["recognition_model"].initial == "ArcFace"
    assert form.fields["sharpness_threshold"].initial == 0.55


@pytest.mark.django_db
def test_form_save_writes_all_fields_to_settings(deduplication_set_group_factory):
    """save() persists all submitted fields into instance.settings JSON."""
    group = deduplication_set_group_factory()

    form = DeduplicationSetGroupSettingsForm(data=VALID_FORM_DATA, instance=group)
    assert form.is_valid(), form.errors
    saved = form.save()

    assert saved.settings["recognition_model"] == "Facenet512"
    assert saved.settings["sharpness_threshold"] == 0.4
    assert saved.settings["eyes_open_threshold"] == 0.6
    assert saved.settings["duplicate_confidence_threshold"] == 0.6


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("face_detection_confidence_threshold", 1.5),
        ("face_detection_confidence_threshold", -0.1),
        ("sharpness_threshold", 1.5),
        ("sharpness_threshold", -0.1),
        ("recognition_model", "UnknownModel"),
        ("detector_backend", "unknown_backend"),
        ("recognition_model", ""),
        ("detector_backend", ""),
    ],
    ids=[
        "confidence_above_1",
        "confidence_below_0",
        "sharpness_above_1",
        "sharpness_below_0",
        "invalid_recognition_model",
        "invalid_detector_backend",
        "empty_recognition_model",
        "empty_detector_backend",
    ],
)
def test_form_validation_rejects_invalid_values(field, value):
    """Form validation rejects out-of-range or invalid-choice values."""
    data = {**VALID_FORM_DATA, field: value}
    form = DeduplicationSetGroupSettingsForm(data=data)
    assert not form.is_valid()
    assert field in form.errors


@pytest.mark.django_db
def test_form_rejects_changes_when_embeddings_exist(
    deduplication_set_group_factory, deduplication_set_factory, encoding_factory
):
    group = deduplication_set_group_factory()
    group.settings = dict(VALID_FORM_DATA)
    group.save()

    ds = deduplication_set_factory(group=group)
    encoding_factory(deduplication_set=ds, embedding=[0.1] * 8)

    changed_data = {**VALID_FORM_DATA, "sharpness_threshold": 0.9}
    form = DeduplicationSetGroupSettingsForm(data=changed_data, instance=group)
    assert not form.is_valid()
    assert "__all__" in form.errors


@pytest.mark.django_db
def test_form_allows_save_when_no_embeddings(deduplication_set_group_factory):
    group = deduplication_set_group_factory()
    group.settings = dict(VALID_FORM_DATA)
    group.save()

    changed_data = {**VALID_FORM_DATA, "sharpness_threshold": 0.9}
    form = DeduplicationSetGroupSettingsForm(data=changed_data, instance=group)
    assert form.is_valid(), form.errors
