import pytest
from constance.test import override_config
from testutils.factories.biographic import BiographicGroupFactory, BiographicSetFactory

from hope_dedup_engine.apps.biographic.config import (
    BiographicConfig,
    get_default_group_settings,
    resolve_config,
)

pytestmark = pytest.mark.django_db

SETTINGS = {"duplicate_score", "max_hits"}


def test_setting_fields_are_the_thresholds_not_the_id():
    assert {f.name for f in BiographicConfig.setting_fields()} == SETTINGS


def test_constance_defaults_match_hope():
    assert get_default_group_settings() == {"duplicate_score": 6.0, "max_hits": 100}


@override_config(DEFAULT_BIOGRAPHIC_DUPLICATE_SCORE=9.5)
def test_defaults_are_read_from_constance_at_call_time():
    assert get_default_group_settings()["duplicate_score"] == 9.5


def test_request_override_beats_group_which_beats_constance():
    group = BiographicGroupFactory(settings={"duplicate_score": 11.0})
    dataset = BiographicSetFactory(group=group)

    with override_config(DEFAULT_BIOGRAPHIC_MAX_HITS=7):
        config = resolve_config(dataset, {"duplicate_score": 14.0})

    assert config.duplicate_score == 14.0  # request
    assert config.max_hits == 7  # constance: the group never snapshotted it
    assert config.dataset_id == dataset.pk


def test_group_setting_beats_constance():
    group = BiographicGroupFactory(settings={"duplicate_score": 11.0, "max_hits": 50})
    dataset = BiographicSetFactory(group=group)
    with override_config(DEFAULT_BIOGRAPHIC_MAX_HITS=7):
        assert resolve_config(dataset).max_hits == 50


def test_group_snapshot_ignores_later_constance_changes():
    group = BiographicGroupFactory(settings=get_default_group_settings())
    dataset = BiographicSetFactory(group=group)
    with override_config(DEFAULT_BIOGRAPHIC_DUPLICATE_SCORE=20.0):
        assert resolve_config(dataset).duplicate_score == 6.0


def test_empty_group_settings_fall_back_to_constance():
    dataset = BiographicSetFactory(group__settings=None)
    assert resolve_config(dataset).as_dict() == {"dataset_id": dataset.pk, **get_default_group_settings()}


def test_a_dropped_setting_in_an_old_snapshot_is_ignored():
    """Groups created before the abort rules were removed still carry them."""
    group = BiographicGroupFactory(settings={"duplicate_score": 6.0, "batch_duplicates_allowed": 5})
    dataset = BiographicSetFactory(group=group)
    assert set(resolve_config(dataset).as_dict()) == {"dataset_id", *SETTINGS}
