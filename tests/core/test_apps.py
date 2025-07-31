from hope_dedup_engine.apps.core.apps import Config


def test_core_app_config_name():
    """Verify the name of the core app configuration."""
    assert Config.name == "hope_dedup_engine.apps.core"
