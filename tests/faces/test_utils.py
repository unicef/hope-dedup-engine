from hope_dedup_engine.apps.faces.utils import DEFAULT_THRESHOLD_SECONDS


def test_default_threshold_seconds():
    """Verify the value of the DEFAULT_THRESHOLD_SECONDS constant."""
    assert DEFAULT_THRESHOLD_SECONDS == 60
