import pytest

from hope_dedup_engine.apps.api.models import DeduplicationSet


@pytest.mark.parametrize(
    "state",
    [
        DeduplicationSet.State.READY,
        DeduplicationSet.State.MODIFIED,
        DeduplicationSet.State.PROCESSING,
        DeduplicationSet.State.FAILED,
    ],
)
@pytest.mark.parametrize(
    ("error", "error_field"),
    [
        (None, None),
        (ValueError(message := "I don't like this value"), f"ValueError: {message}\n"),
    ],
)
def test_deduplicationset_set_state(
    deduplication_set: DeduplicationSet, state: DeduplicationSet.State, error: Exception | None, error_field: str | None
):
    deduplication_set.set_state(state, error)

    assert deduplication_set.state == state
    assert deduplication_set.error == error_field
