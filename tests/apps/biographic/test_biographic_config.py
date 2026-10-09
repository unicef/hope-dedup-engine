import pytest
from constance.test import override_config

from hope_dedup_engine.apps.biographic.config import BiographicConfig, resolve_config
from testutils.factories.biographic import BiographicSetFactory

pytestmark = pytest.mark.django_db


def test_duplicate_score_defaults_to_hope_value() -> None:
    config = BiographicConfig()
    assert config.duplicate_score == 6.0
    assert not hasattr(config, "possible_duplicate_score")


def test_config_precedence_is_request_then_group_then_constance() -> None:
    dataset = BiographicSetFactory()
    dataset.group.settings = {"duplicate_score": 8.0, "max_hits": 20}
    dataset.group.save(update_fields=["settings"])

    with override_config(DEFAULT_BIOGRAPHIC_DUPLICATE_SCORE=7.0):
        from_group = resolve_config(dataset)
        from_request = resolve_config(dataset, {"duplicate_score": 9.0, "max_hits": 3})
        dataset.group.settings = {}
        dataset.group.save(update_fields=["settings"])
        from_constance = resolve_config(dataset)

    assert from_group.duplicate_score == 8.0
    assert from_group.max_hits == 20
    assert from_request.duplicate_score == 9.0
    assert from_request.max_hits == 3
    assert from_constance.duplicate_score == 7.0
    assert from_constance.max_hits == 100
    assert from_constance.dataset_id == dataset.pk


def test_request_override_rejects_unknown_and_non_numeric_values() -> None:
    dataset = BiographicSetFactory()
    with pytest.raises(ValueError, match="Unknown biographic settings"):
        resolve_config(dataset, {"not_a_setting": 1})
    with pytest.raises(ValueError, match="possible_duplicate_score"):
        resolve_config(dataset, {"possible_duplicate_score": 4.0})
    with pytest.raises(ValueError, match="duplicate_score"):
        resolve_config(dataset, {"duplicate_score": "6"})
    with pytest.raises(ValueError, match="max_hits"):
        resolve_config(dataset, {"max_hits": True})
