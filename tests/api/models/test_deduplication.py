import pytest

from hope_dedup_engine.apps.api.deduplication.config import get_default_group_settings
from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding
from hope_dedup_engine.apps.api.models.deduplication import EncodingErrorGroup, GroupSettingsError


@pytest.fixture
def group_with_settings(deduplication_set_group_factory):
    group = deduplication_set_group_factory()
    group.settings = get_default_group_settings()
    group.save()
    return group


@pytest.fixture
def group_with_settings_locked(deduplication_set_group_factory):
    group = deduplication_set_group_factory()
    group.settings = get_default_group_settings()
    group.processing_locked = True
    group.save()
    return group


@pytest.fixture
def group_with_settings_none(deduplication_set_group_factory):
    group = deduplication_set_group_factory()
    group.settings = None
    group.save()
    return group


@pytest.fixture
def group_with_approved_ds(group_with_settings, deduplication_set_factory):
    deduplication_set_factory(group=group_with_settings, state=DeduplicationSet.State.APPROVED)
    return group_with_settings


@pytest.fixture
def group_ds_deduplicated_with_data(group_with_settings, deduplication_set_factory, encoding_factory, finding_factory):
    ds = deduplication_set_factory(group=group_with_settings, state=DeduplicationSet.State.DEDUPLICATED)
    enc = encoding_factory(deduplication_set=ds, embedding=[0.1] * 8)
    finding_factory(deduplication_set=ds, first_encoding=enc)
    return group_with_settings, ds, enc


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (DeduplicationSet.State.EMPTY, DeduplicationSet.State.UPLOADING_IN_PROGRESS),
        (DeduplicationSet.State.UPLOADING_IN_PROGRESS, DeduplicationSet.State.READY),
        (DeduplicationSet.State.READY, DeduplicationSet.State.ENCODING_IN_PROGRESS),
        (DeduplicationSet.State.ENCODING_IN_PROGRESS, DeduplicationSet.State.ENCODED),
        (DeduplicationSet.State.ENCODING_IN_PROGRESS, DeduplicationSet.State.ENCODING_FAILED),
        (DeduplicationSet.State.ENCODED, DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS),
        (DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS, DeduplicationSet.State.DEDUPLICATED),
        (DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS, DeduplicationSet.State.DEDUPLICATION_FAILED),
        (DeduplicationSet.State.DEDUPLICATED, DeduplicationSet.State.APPROVED),
        (DeduplicationSet.State.DEDUPLICATED, DeduplicationSet.State.REJECTED),
        (DeduplicationSet.State.DEDUPLICATED, DeduplicationSet.State.READY),
        (DeduplicationSet.State.DEDUPLICATED, DeduplicationSet.State.ENCODED),
    ],
)
@pytest.mark.parametrize(
    ("error", "error_field"),
    [
        (None, None),
        (ValueError(message := "I don't like this value"), f"ValueError: {message}\n"),
    ],
)
def test_deduplicationset_set_state_valid_transition(
    deduplication_set_factory, from_state, to_state, error, error_field
):
    ds = deduplication_set_factory(state=from_state)
    ds.set_state(to_state, error)

    assert ds.state == to_state
    assert ds.error == error_field


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (DeduplicationSet.State.READY, DeduplicationSet.State.DEDUPLICATED),
        (DeduplicationSet.State.APPROVED, DeduplicationSet.State.READY),
        (DeduplicationSet.State.ENCODING_IN_PROGRESS, DeduplicationSet.State.READY),
    ],
)
def test_deduplicationset_set_state_invalid_transition(deduplication_set_factory, from_state, to_state):
    ds = deduplication_set_factory(state=from_state)
    with pytest.raises(ValueError, match="Invalid state transition"):
        ds.set_state(to_state)


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (DeduplicationSet.State.APPROVED, DeduplicationSet.State.READY),
        (DeduplicationSet.State.DEDUPLICATED, DeduplicationSet.State.READY),
        (DeduplicationSet.State.ENCODING_IN_PROGRESS, DeduplicationSet.State.READY),
    ],
)
def test_deduplicationset_set_state_force_bypasses_validation(deduplication_set_factory, from_state, to_state):
    ds = deduplication_set_factory(state=from_state)
    ds.set_state(to_state, force=True)

    ds.refresh_from_db()
    assert ds.state == to_state
    assert ds.error is None


def test_encoding_error_groups_are_non_overlapping():
    all_groups = [EncodingErrorGroup.FACE_DETECT, EncodingErrorGroup.IMAGE_QUALITY, EncodingErrorGroup.SYSTEM]
    all_codes = [code for group in all_groups for code in group]
    assert len(all_codes) == len(set(all_codes)), "Status codes appear in more than one error group"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status_code", "should_be_excluded"),
    [
        (None, False),
        (Encoding.StatusCode.BAD_IMAGE_QUALITY, True),
        (Encoding.StatusCode.NO_FACE_DETECTED, True),
        (Encoding.StatusCode.MULTIPLE_FACES_DETECTED, True),
        (Encoding.StatusCode.FACE_NOT_ACCEPTED, True),
        (Encoding.StatusCode.FILE_NOT_FOUND, False),
        (Encoding.StatusCode.GENERIC_ERROR, False),
    ],
    ids=[
        "no_status_included",
        "bad_image_quality_excluded",
        "no_face_detected_excluded",
        "multiple_faces_excluded",
        "face_not_accepted_excluded",
        "file_not_found_retried",
        "generic_error_retried",
    ],
)
def test_encodings_without_embeddings_exclusion(
    deduplication_set_factory, encoding_factory, status_code, should_be_excluded
):
    ds = deduplication_set_factory()
    encoding_factory(deduplication_set=ds, embedding=None, embedding_status_code=status_code)

    qs = ds.encodings_without_embeddings()

    if should_be_excluded:
        assert qs.count() == 0
    else:
        assert qs.count() == 1


@pytest.mark.django_db
def test_update_settings_raises_when_approved_sets_exist(group_with_approved_ds):
    with pytest.raises(GroupSettingsError, match="approved"):
        group_with_approved_ds.update_settings({"sharpness_threshold": 0.5})


@pytest.mark.django_db
def test_update_settings_raises_when_processing_locked(group_with_settings_locked):
    with pytest.raises(GroupSettingsError, match="processing job is running"):
        group_with_settings_locked.update_settings({"sharpness_threshold": 0.5})


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state",
    [
        DeduplicationSet.State.EMPTY,
        DeduplicationSet.State.UPLOADING_IN_PROGRESS,
        DeduplicationSet.State.READY,
        DeduplicationSet.State.REJECTED,
        DeduplicationSet.State.ENCODING_FAILED,
        DeduplicationSet.State.DEDUPLICATION_FAILED,
    ],
)
def test_update_settings_allowed_for_states_without_data_to_clean(
    group_with_settings, deduplication_set_factory, state
):
    """Settings change is allowed for states with no embeddings to clean."""
    deduplication_set_factory(group=group_with_settings, state=state)
    group_with_settings.update_settings({"sharpness_threshold": 0.7})

    group_with_settings.refresh_from_db()
    assert group_with_settings.settings["sharpness_threshold"] == 0.7


@pytest.mark.django_db
def test_update_settings_merges_settings(group_with_settings):
    original = dict(group_with_settings.settings)

    group_with_settings.update_settings({"sharpness_threshold": 0.42})

    group_with_settings.refresh_from_db()
    assert group_with_settings.settings["sharpness_threshold"] == 0.42
    for key, value in original.items():
        if key != "sharpness_threshold":
            assert group_with_settings.settings[key] == value


@pytest.mark.django_db
def test_update_settings_initializes_defaults_when_settings_is_none(group_with_settings_none):
    group_with_settings_none.update_settings({"sharpness_threshold": 0.3})

    group_with_settings_none.refresh_from_db()
    assert group_with_settings_none.settings is not None
    assert group_with_settings_none.settings["sharpness_threshold"] == 0.3


@pytest.mark.django_db
def test_clear_active_set_noop_when_no_dedup_sets(group_with_settings):
    group_with_settings._clear_active_set_on_settings_change()
    assert not group_with_settings.processing_locked


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state",
    [
        DeduplicationSet.State.EMPTY,
        DeduplicationSet.State.UPLOADING_IN_PROGRESS,
        DeduplicationSet.State.READY,
        DeduplicationSet.State.REJECTED,
        DeduplicationSet.State.ENCODING_FAILED,
        DeduplicationSet.State.DEDUPLICATION_FAILED,
    ],
)
def test_clear_active_set_noop_for_non_cleanable_states(group_with_settings, deduplication_set_factory, state):
    """Cleanup only targets ENCODED/DEDUPLICATED sets; other states are left alone."""
    ds = deduplication_set_factory(group=group_with_settings, state=state)
    group_with_settings._clear_active_set_on_settings_change()

    ds.refresh_from_db()
    assert ds.state == state


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state",
    [
        DeduplicationSet.State.ENCODED,
        DeduplicationSet.State.DEDUPLICATED,
    ],
)
def test_clear_active_set_clears_data_and_transitions_to_ready(
    group_with_settings, deduplication_set_factory, encoding_factory, finding_factory, state
):
    ds = deduplication_set_factory(group=group_with_settings, state=state)
    enc = encoding_factory(deduplication_set=ds, embedding=[0.1] * 8)
    if state == DeduplicationSet.State.DEDUPLICATED:
        finding_factory(deduplication_set=ds, first_encoding=enc)

    group_with_settings._clear_active_set_on_settings_change()

    enc.refresh_from_db()
    assert enc.embedding is None
    assert ds.finding_set.count() == 0
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.READY


@pytest.mark.django_db
def test_update_settings_full_flow_clears_deduplicated_set(group_ds_deduplicated_with_data):
    group, ds, enc = group_ds_deduplicated_with_data

    group.update_settings({"sharpness_threshold": 0.4})

    enc.refresh_from_db()
    assert enc.embedding is None
    assert ds.finding_set.count() == 0
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.READY
