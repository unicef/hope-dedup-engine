import pytest

from hope_dedup_engine.apps.api.deduplication.config import (
    DeduplicationSetConfig,
    get_default_group_settings,
)
from hope_dedup_engine.apps.api.models import DeduplicationSet
from testutils.factories.api import DeduplicationSetFactory


@pytest.mark.django_db
def test_get_default_group_settings_contains_all_setting_fields():
    result = get_default_group_settings()
    expected_keys = {f.name for f in DeduplicationSetConfig.setting_fields()}
    assert set(result.keys()) == expected_keys


@pytest.fixture
def ds_with_model_settings(db) -> DeduplicationSet:
    return DeduplicationSetFactory.create(
        group__settings={
            "recognition_model": "ArcFace",
            "detector_backend": "ssd",
            "distance_metric": "euclidean",
            "face_detection_confidence_threshold": 0.8,
        }
    )


@pytest.fixture
def ds_with_duplicate_confidence_settings(db) -> DeduplicationSet:
    return DeduplicationSetFactory.create(group__settings={"duplicate_confidence_threshold": 0.65})


@pytest.fixture
def ds_with_ofiq_settings(db) -> DeduplicationSet:
    return DeduplicationSetFactory.create(group__settings={"sharpness_threshold": 0.5, "eyes_open_threshold": 0.7})


@pytest.fixture
def ds_with_empty_settings(db) -> DeduplicationSet:
    return DeduplicationSetFactory.create(group__settings={})


@pytest.fixture
def ds_default(db) -> DeduplicationSet:
    return DeduplicationSetFactory.create()


@pytest.mark.django_db
def test_from_deduplication_set_uses_group_settings(ds_with_model_settings: DeduplicationSet):
    config = DeduplicationSetConfig.from_deduplication_set(ds_with_model_settings)

    assert config.recognition_model == "ArcFace"
    assert config.detector_backend == "ssd"
    assert config.distance_metric == "euclidean"
    assert config.face_detection_confidence_threshold == 0.8


@pytest.mark.django_db
def test_from_deduplication_set_scales_duplicate_confidence(ds_with_duplicate_confidence_settings: DeduplicationSet):
    config = DeduplicationSetConfig.from_deduplication_set(ds_with_duplicate_confidence_settings)

    assert config.duplicate_confidence_threshold == pytest.approx(65.0)


@pytest.mark.django_db
def test_from_deduplication_set_scales_ofiq_thresholds(ds_with_ofiq_settings: DeduplicationSet):
    config = DeduplicationSetConfig.from_deduplication_set(ds_with_ofiq_settings)

    assert config.sharpness_threshold == pytest.approx(50.0)
    assert config.eyes_open_threshold == pytest.approx(70.0)


@pytest.mark.django_db
def test_from_deduplication_set_falls_back_to_constance_defaults(ds_with_empty_settings: DeduplicationSet):
    config = DeduplicationSetConfig.from_deduplication_set(ds_with_empty_settings)
    default_config = DeduplicationSetConfig()

    assert config.recognition_model == default_config.recognition_model
    assert config.detector_backend == default_config.detector_backend
    assert config.sharpness_threshold == default_config.sharpness_threshold


@pytest.mark.django_db
def test_from_deduplication_set_stores_pk(ds_default: DeduplicationSet):
    config = DeduplicationSetConfig.from_deduplication_set(ds_default)
    assert config.deduplication_set_id == ds_default.pk


def test_setting_fields_filters_by_metadata():
    api_fields = DeduplicationSetConfig.setting_fields(api=True)
    admin_fields = DeduplicationSetConfig.setting_fields(admin=True)
    quality_fields = DeduplicationSetConfig.setting_fields(category="quality")

    assert all(f.metadata.get("api") for f in api_fields)
    assert all(f.metadata.get("admin") for f in admin_fields)
    assert all(f.metadata.get("category") == "quality" for f in quality_fields)
    assert len(api_fields) > 0
    assert len(admin_fields) > 0
    assert len(quality_fields) > 0
