import pytest

from hope_dedup_engine.apps.api.admin.forms import DeduplicationSetGroupSettingsForm

VALID_FORM_DATA = {
    "recognition_model": "Facenet512",
    "detector_backend": "retinaface",
    "distance_metric": "cosine",
    "face_detection_confidence_threshold": 0.8,
    "face_coverage_threshold": 0.1,
    "duplicate_confidence_threshold": 0.6,
    "sharpness_threshold": 40,
    "dynamic_range_threshold": 30,
    "no_head_cover_threshold": 50,
    "eyes_open_threshold": 60,
    "inter_eye_distance_threshold": 70,
    "unified_quality_score_threshold": 80,
}


@pytest.mark.django_db
def test_form_populates_initial_from_settings(deduplication_set_group_factory):
    """__init__ sets field initials from instance.settings."""
    group = deduplication_set_group_factory()
    group.settings = {"recognition_model": "ArcFace", "sharpness_threshold": 55}
    group.save()

    form = DeduplicationSetGroupSettingsForm(instance=group)

    assert form.fields["recognition_model"].initial == "ArcFace"
    assert form.fields["sharpness_threshold"].initial == 55


@pytest.mark.django_db
def test_form_save_writes_all_fields_to_settings(deduplication_set_group_factory):
    """save() persists all submitted fields into instance.settings JSON."""
    group = deduplication_set_group_factory()

    form = DeduplicationSetGroupSettingsForm(data=VALID_FORM_DATA, instance=group)
    assert form.is_valid(), form.errors
    saved = form.save()

    assert saved.settings["recognition_model"] == "Facenet512"
    assert saved.settings["sharpness_threshold"] == 40
    assert saved.settings["eyes_open_threshold"] == 60
    assert saved.settings["duplicate_confidence_threshold"] == 0.6


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("face_detection_confidence_threshold", 1.5),
        ("face_detection_confidence_threshold", -0.1),
        ("sharpness_threshold", 101),
        ("sharpness_threshold", -1),
        ("recognition_model", "UnknownModel"),
        ("detector_backend", "unknown_backend"),
        ("recognition_model", ""),
        ("detector_backend", ""),
    ],
    ids=[
        "confidence_above_1",
        "confidence_below_0",
        "sharpness_above_100",
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
