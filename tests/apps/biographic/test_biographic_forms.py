import pytest
from constance.test import override_config
from testutils.factories.biographic import BiographicGroupFactory

from hope_dedup_engine.apps.biographic.config import BiographicConfig
from hope_dedup_engine.apps.biographic.forms import BiographicGroupSettingsForm

pytestmark = pytest.mark.django_db

VALID = {"duplicate_score": 7.5, "max_hits": 50}


def test_one_field_per_setting():
    form = BiographicGroupSettingsForm()
    assert set(form.fields) == {f.name for f in BiographicConfig.setting_fields()}


def test_initial_comes_from_the_group_snapshot():
    group = BiographicGroupFactory(settings={"duplicate_score": 9.0, "max_hits": 20})
    form = BiographicGroupSettingsForm(instance=group)
    assert form.fields["duplicate_score"].initial == 9.0
    assert form.fields["max_hits"].initial == 20


@override_config(DEFAULT_BIOGRAPHIC_MAX_HITS=25)
def test_a_setting_missing_from_the_snapshot_shows_the_constance_default():
    group = BiographicGroupFactory(settings={"duplicate_score": 9.0})
    form = BiographicGroupSettingsForm(instance=group)
    assert form.fields["max_hits"].initial == 25


def test_save_writes_every_setting_into_the_snapshot():
    group = BiographicGroupFactory(settings={"duplicate_score": 6.0, "max_hits": 100, "legacy": 1})
    form = BiographicGroupSettingsForm(data=VALID, instance=group)
    assert form.is_valid(), form.errors

    form.save()

    group.refresh_from_db()
    assert group.settings == {"duplicate_score": 7.5, "max_hits": 50, "legacy": 1}


@pytest.mark.parametrize(
    ("field", "value"),
    [("duplicate_score", -1), ("max_hits", 0), ("max_hits", 2.5), ("duplicate_score", ""), ("max_hits", "")],
)
def test_invalid_values_are_refused(field, value):
    form = BiographicGroupSettingsForm(data={**VALID, field: value}, instance=BiographicGroupFactory())
    assert not form.is_valid()
    assert field in form.errors


def test_the_next_run_uses_the_new_threshold():
    """Settings are read when a run starts, so the form change is enough: no block, no sync."""
    group = BiographicGroupFactory(settings={"duplicate_score": 6.0, "max_hits": 100})
    form = BiographicGroupSettingsForm(data=VALID, instance=group)
    assert form.is_valid()
    form.save()

    dataset = group.sets.create()
    config = BiographicConfig.for_set(dataset)
    assert (config.duplicate_score, config.max_hits) == (7.5, 50)
