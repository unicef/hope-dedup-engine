import pytest

from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding
from hope_dedup_engine.apps.api.models.deduplication import EncodingErrorGroup


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
