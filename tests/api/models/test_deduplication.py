from unittest.mock import patch

import pytest

from hope_dedup_engine.apps.api.deduplication.config import get_default_group_settings
from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding
from hope_dedup_engine.apps.api.models.deduplication import EncodingErrorGroup, GroupSettingsError


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (DeduplicationSet.State.EMPTY, DeduplicationSet.State.UPLOADING_IN_PROGRESS),
        (DeduplicationSet.State.EMPTY, DeduplicationSet.State.READY),
        (DeduplicationSet.State.UPLOADING_IN_PROGRESS, DeduplicationSet.State.READY),
        (DeduplicationSet.State.READY, DeduplicationSet.State.ENCODING_IN_PROGRESS),
        (DeduplicationSet.State.ENCODING_IN_PROGRESS, DeduplicationSet.State.ENCODED),
        (DeduplicationSet.State.ENCODING_IN_PROGRESS, DeduplicationSet.State.ENCODING_FAILED),
        (DeduplicationSet.State.ENCODED, DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS),
        (DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS, DeduplicationSet.State.DEDUPLICATED),
        (DeduplicationSet.State.DEDUPLICATION_IN_PROGRESS, DeduplicationSet.State.DEDUPLICATION_FAILED),
        (DeduplicationSet.State.DEDUPLICATED, DeduplicationSet.State.APPROVED),
        (DeduplicationSet.State.DEDUPLICATED, DeduplicationSet.State.REJECTED),
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
def test_update_settings_raises_when_approved_sets_exist(deduplication_set_group_factory, deduplication_set_factory):
    group = deduplication_set_group_factory()
    group.settings = get_default_group_settings()
    group.save()
    deduplication_set_factory(group=group, state=DeduplicationSet.State.APPROVED)

    with pytest.raises(GroupSettingsError, match="APPROVED or DEDUPLICATED"):
        group.update_settings({"sharpness_threshold": 0.5})


@pytest.mark.django_db
def test_update_settings_merges_settings(deduplication_set_group_factory):
    group = deduplication_set_group_factory()
    group.settings = get_default_group_settings()
    group.save()
    original = dict(group.settings)

    group.update_settings({"sharpness_threshold": 0.42})

    group.refresh_from_db()
    assert group.settings["sharpness_threshold"] == 0.42
    for key, value in original.items():
        if key != "sharpness_threshold":
            assert group.settings[key] == value


@pytest.mark.django_db
def test_update_settings_initializes_defaults_when_settings_is_none(deduplication_set_group_factory):
    group = deduplication_set_group_factory()
    group.settings = None
    group.save()

    group.update_settings({"sharpness_threshold": 0.3})

    group.refresh_from_db()
    assert group.settings is not None
    assert group.settings["sharpness_threshold"] == 0.3


@pytest.mark.django_db
def test_trigger_re_encoding_noop_when_no_dedup_sets(deduplication_set_group_factory):
    group = deduplication_set_group_factory()
    group.settings = get_default_group_settings()
    group.save()

    group._trigger_re_encoding()

    assert not group.processing_locked


@pytest.mark.django_db
def test_trigger_re_encoding_noop_when_no_embeddings(
    deduplication_set_group_factory, deduplication_set_factory, encoding_factory
):
    group = deduplication_set_group_factory()
    group.settings = get_default_group_settings()
    group.save()
    ds = deduplication_set_factory(group=group)
    encoding_factory(deduplication_set=ds, embedding=None, embedding_status_code=None)

    group._trigger_re_encoding()

    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.READY
    assert not group.processing_locked


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.api.models.jobs.MainJob.objects.create")
def test_trigger_re_encoding_clears_data_and_queues_job_when_lock_acquired(
    mock_create,
    deduplication_set_group_factory,
    deduplication_set_factory,
    encoding_factory,
    finding_factory,
):
    mock_job = mock_create.return_value
    group = deduplication_set_group_factory()
    group.settings = get_default_group_settings()
    group.save()
    ds = deduplication_set_factory(group=group)
    enc = encoding_factory(deduplication_set=ds, embedding=[0.1] * 8)
    finding_factory(deduplication_set=ds, first_encoding=enc)

    group._trigger_re_encoding()

    enc.refresh_from_db()
    assert enc.embedding is None
    assert ds.finding_set.count() == 0
    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.ENCODING_IN_PROGRESS
    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["encode_only"] is True
    mock_job.queue.assert_called_once()


@pytest.mark.django_db
@patch("hope_dedup_engine.apps.api.models.jobs.MainJob.objects.create")
def test_trigger_re_encoding_resets_to_ready_when_lock_not_acquired(
    mock_create,
    deduplication_set_group_factory,
    deduplication_set_factory,
    encoding_factory,
):
    group = deduplication_set_group_factory()
    group.settings = get_default_group_settings()
    group.processing_locked = True
    group.save()
    ds = deduplication_set_factory(group=group)
    encoding_factory(deduplication_set=ds, embedding=[0.1] * 8)

    group._trigger_re_encoding()

    ds.refresh_from_db()
    assert ds.state == DeduplicationSet.State.READY
    assert ds.error is None
    mock_create.assert_not_called()
