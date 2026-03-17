import pytest

from hope_dedup_engine.apps.api.deduplication.config import (
    SETTINGS_FIELDS,
    DeduplicationSetConfig,
    get_default_group_settings,
)


@pytest.mark.django_db
def test_get_default_group_settings_contains_all_fields():
    result = get_default_group_settings()
    assert set(result.keys()) == set(SETTINGS_FIELDS)


@pytest.mark.django_db
def test_from_deduplication_set_uses_group_settings(deduplication_set_factory):
    ds = deduplication_set_factory()
    ds.group.settings = {
        "recognition_model": "ArcFace",
        "detector_backend": "ssd",
        "distance_metric": "euclidean",
        "face_detection_confidence_threshold": 0.8,
    }
    ds.group.save()

    config = DeduplicationSetConfig.from_deduplication_set(ds)

    assert config.recognition_model == "ArcFace"
    assert config.detector_backend == "ssd"
    assert config.distance_metric == "euclidean"
    assert config.face_detection_confidence_threshold == 0.8


@pytest.mark.django_db
def test_from_deduplication_set_scales_duplicate_confidence(deduplication_set_factory):
    ds = deduplication_set_factory()
    ds.group.settings = {"duplicate_confidence_threshold": 0.65}
    ds.group.save()

    config = DeduplicationSetConfig.from_deduplication_set(ds)

    assert config.duplicate_confidence_threshold == pytest.approx(65.0)


@pytest.mark.django_db
def test_from_deduplication_set_falls_back_to_constance_defaults(deduplication_set_factory):
    ds = deduplication_set_factory()
    ds.group.settings = {}
    ds.group.save()

    config = DeduplicationSetConfig.from_deduplication_set(ds)
    default_config = DeduplicationSetConfig()

    assert config.recognition_model == default_config.recognition_model
    assert config.detector_backend == default_config.detector_backend
    assert config.sharpness_threshold == default_config.sharpness_threshold


@pytest.mark.django_db
def test_from_deduplication_set_stores_pk(deduplication_set_factory):
    ds = deduplication_set_factory()
    config = DeduplicationSetConfig.from_deduplication_set(ds)
    assert config.deduplication_set_id == ds.pk
