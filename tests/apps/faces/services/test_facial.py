from unittest.mock import Mock

import numpy as np
import pytest
from azure.core.exceptions import ResourceNotFoundError

from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding
from hope_dedup_engine.apps.faces.services.facial import (
    dedupe_all,
    encode_face,
    encode_faces,
    face_coverage_ratio,
    find_duplicate_pairs,
    load_encodings,
)

MODEL_NAME = "model"
DETECTOR_BACKEND = "backend"
ALIGN = True
IMG_SIDE = 300


def fa(*, w: int, h: int, x: int = 0, y: int = 0) -> dict[str, int]:
    return {"x": x, "y": y, "w": w, "h": h}


def cov(*, w: int, h: int, side: int = IMG_SIDE) -> float:
    return round((w * h) / (side * side), 4)


@pytest.fixture
def mock_deepface(mocker):
    """Fixture to mock the DeepFace module used by the facial service."""
    return mocker.patch("hope_dedup_engine.apps.faces.services.facial.DeepFace")


@pytest.fixture
def sample_image() -> np.ndarray:
    """Sample image data for face encoding tests."""
    img = np.zeros((IMG_SIDE, IMG_SIDE, 3), dtype=np.uint8)
    img[0, 0] = 255
    return img


@pytest.fixture
def mock_storage(mocker, sample_image):
    """Fixture to mock ImagesStorageManager and return a numpy image by default."""
    storage_mock = mocker.patch("hope_dedup_engine.apps.faces.services.facial.ImagesStorageManager").return_value
    storage_mock.load_image.return_value = sample_image
    return storage_mock


@pytest.fixture
def call_encode_face(mock_deepface, sample_image):
    """Call encode_face with a configurable DeepFace.represent return value."""

    def _call(represent_return, *, fc_th: float = 0.1, cov_th: float = 0.0):
        mock_deepface.represent.return_value = represent_return
        return encode_face(
            sample_image,
            face_confidence_threshold=fc_th,
            face_coverage_threshold=cov_th,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR_BACKEND,
            align=ALIGN,
        )

    return _call


# --- face_coverage_ratio -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fa_", "img_w", "img_h", "expected"),
    [
        ({"w": 10, "h": 10}, 100, 100, 0.01),
        ({"w": 0, "h": 10}, 100, 100, 0.0),
        ({"w": 10, "h": 10}, 0, 100, 0.0),
    ],
    ids=["normal_case", "zero_width_face", "zero_image_width"],
)
def test_face_coverage_ratio(fa_, img_w, img_h, expected):
    """Test face_coverage_ratio computes bbox/image area ratio."""
    assert face_coverage_ratio(fa=fa_, img_w=img_w, img_h=img_h) == pytest.approx(expected)


# --- encode_face ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("represent_return", "fc_th", "cov_th", "exp_embedding", "exp_status", "exp_coverage"),
    [
        ([], 0.1, 0.0, None, Encoding.StatusCode.NO_FACE_DETECTED, None),
        (None, 0.1, 0.0, None, Encoding.StatusCode.GENERIC_ERROR, None),
        (
            [{"embedding": [1.0], "face_confidence": 0.0, "facial_area": fa(w=10, h=10)}],
            0.1,
            0.0,
            None,
            Encoding.StatusCode.NO_FACE_DETECTED,
            None,
        ),
        (
            [{"embedding": [1.0], "face_confidence": 0.05, "facial_area": fa(w=10, h=10)}],
            0.1,
            0.0,
            None,
            Encoding.StatusCode.FACE_NOT_ACCEPTED,
            None,
        ),
        ([{"embedding": [1.0], "face_confidence": 0.99}], 0.1, 0.0, None, Encoding.StatusCode.GENERIC_ERROR, None),
        (
            [{"embedding": [1.0], "face_confidence": 0.99, "facial_area": fa(w=10, h=10)}],
            0.1,
            0.05,
            None,
            Encoding.StatusCode.INSUFFICIENT_FACE_COVERAGE,
            cov(w=10, h=10),
        ),
        (
            [{"embedding": [1.0], "face_confidence": 0.99, "facial_area": fa(w=120, h=170)}],
            0.1,
            0.0,
            [1.0],
            None,
            pytest.approx(cov(w=120, h=170)),
        ),
    ],
    ids=[
        "no_face_detected",
        "generic_error",
        "no_face_detected_zero_confidence",
        "face_not_accepted",
        "generic_error_no_facial_area",
        "insufficient_face_coverage",
        "successful_encoding",
    ],
)
def test_encode_face_outcomes(
    call_encode_face, represent_return, fc_th, cov_th, exp_embedding, exp_status, exp_coverage
):
    """Test encode_face status/coverage outcomes across represent shapes and thresholds."""
    embedding, status, coverage = call_encode_face(represent_return, fc_th=fc_th, cov_th=cov_th)
    assert embedding == exp_embedding
    assert status == exp_status
    assert coverage == exp_coverage


# --- encode_faces ----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_encode_faces_success(mock_deepface, mock_storage, deduplication_set_factory, encoding_factory):
    """Test successful encoding of faces for a list of files."""
    deduplication_set = deduplication_set_factory()
    encoding0 = encoding_factory(deduplication_set=deduplication_set, filename="file1.jpg", embedding=None)
    encoding1 = encoding_factory(deduplication_set=deduplication_set, filename="file2.jpg", embedding=None)

    mock_deepface.represent.side_effect = [
        [{"embedding": [1.0], "face_confidence": 0.1, "facial_area": fa(w=120, h=170)}],
        [{"embedding": [2.0], "face_confidence": 0.1, "facial_area": fa(w=120, h=170)}],
    ]

    encode_faces(deduplication_set, [encoding0.id, encoding1.id], 0.1, 0.0, MODEL_NAME, DETECTOR_BACKEND, ALIGN)

    encoding0.refresh_from_db()
    encoding1.refresh_from_db()
    assert encoding0.embedding == [1.0]
    assert encoding1.embedding == [2.0]
    assert mock_deepface.represent.call_count == 2


@pytest.mark.parametrize(
    ("represent_kwargs", "coverage_th", "expected_status"),
    [
        (
            {
                "return_value": [
                    {"embedding": [1.0], "face_confidence": 0.5},
                    {"embedding": [2.0], "face_confidence": 0.5},
                ]
            },
            0.0,
            Encoding.StatusCode.MULTIPLE_FACES_DETECTED,
        ),
        ({"side_effect": TypeError("generic error")}, 0.0, Encoding.StatusCode.GENERIC_ERROR),
        (
            {"return_value": [{"embedding": [1.0], "face_confidence": 0.0, "facial_area": fa(w=10, h=10)}]},
            0.0,
            Encoding.StatusCode.NO_FACE_DETECTED,
        ),
        (
            {"return_value": [{"embedding": [1.0], "face_confidence": 0.3, "facial_area": fa(w=10, h=10)}]},
            0.0,
            Encoding.StatusCode.FACE_NOT_ACCEPTED,
        ),
        ({"return_value": [{"embedding": [1.0], "face_confidence": 0.99}]}, 0.0, Encoding.StatusCode.GENERIC_ERROR),
        (
            {"return_value": [{"embedding": [1.0], "face_confidence": 0.99, "facial_area": fa(w=10, h=10)}]},
            0.05,
            Encoding.StatusCode.INSUFFICIENT_FACE_COVERAGE,
        ),
    ],
    ids=[
        "multiple_faces_detected",
        "generic_error",
        "no_face_detected",
        "face_not_accepted",
        "generic_error_no_facial_area",
        "insufficient_face_coverage",
    ],
)
@pytest.mark.django_db
def test_encode_faces_deepface_outcomes(
    mock_deepface, mock_storage, encoding_factory, represent_kwargs, coverage_th, expected_status
):
    """Test encode_faces persists status codes for represent outcomes."""
    encoding = encoding_factory(filename="file1.jpg", embedding=None)
    mock_deepface.represent.configure_mock(**represent_kwargs)

    encode_faces(encoding.deduplication_set, [encoding.id], 0.9, coverage_th, MODEL_NAME, DETECTOR_BACKEND, ALIGN)

    encoding.refresh_from_db()
    assert encoding.embedding_status_code == expected_status.value


@pytest.mark.django_db
def test_encode_faces_file_not_found(mock_deepface, mock_storage, encoding_factory):
    """Test handling of ResourceNotFoundError from storage."""
    encoding = encoding_factory(filename="file1.jpg", embedding=None)
    mock_storage.load_image.side_effect = ResourceNotFoundError("File not found")

    encode_faces(encoding.deduplication_set, [encoding.id], 0.9, 0.0, MODEL_NAME, DETECTOR_BACKEND, ALIGN)

    encoding.refresh_from_db()
    assert encoding.embedding_status_code == Encoding.StatusCode.FILE_NOT_FOUND.value
    mock_deepface.represent.assert_not_called()


def test_encode_faces_sets_status_code_from_quality_gate(mocker, mock_deepface, mock_storage, encoding_factory):
    encoding = encoding_factory(filename="file1.jpg", embedding=None)
    mocker.patch(
        "hope_dedup_engine.apps.faces.services.facial.image_quality_result",
        return_value=(Encoding.StatusCode.IMAGE_QUALITY_TOO_LOW, 1.0),
    )
    encode_faces(encoding.deduplication_set, [encoding.id], 0.9, 0.0, MODEL_NAME, DETECTOR_BACKEND, ALIGN)
    encoding.refresh_from_db()
    assert encoding.embedding_status_code == Encoding.StatusCode.IMAGE_QUALITY_TOO_LOW.value
    mock_deepface.represent.assert_not_called()


# --- dedupe_all (matrix-based deduplication) --------------------------------------------------------


@pytest.fixture
def mock_deepface_verification(mocker):
    """Fixture to mock the DeepFace verification module functions."""
    mock_find_distance = mocker.patch("hope_dedup_engine.apps.faces.services.facial.find_distance")
    mock_find_threshold = mocker.patch("hope_dedup_engine.apps.faces.services.facial.find_threshold")
    mock_find_confidence = mocker.patch("hope_dedup_engine.apps.faces.services.facial.find_confidence")
    return mock_find_distance, mock_find_threshold, mock_find_confidence


@pytest.fixture
def mock_dedup_config():
    """Fixture to create a mock DeduplicationSetConfig."""
    config = Mock()
    config.deduplicate.model_name = "Facenet512"
    config.deduplicate.distance_metric = "cosine"
    config.duplicate_confidence_threshold = 50.0
    return config


@pytest.mark.django_db
def test_dedupe_all_no_encodings(deduplication_set_factory, mock_deepface_verification, mock_dedup_config):
    """Test dedupe_all returns 0 when no encodings exist."""
    ds = deduplication_set_factory()

    count = dedupe_all(ds, mock_dedup_config)

    assert count == 0
    assert ds.finding_set.count() == 0


@pytest.mark.django_db
def test_dedupe_all_single_encoding(
    deduplication_set_factory, encoding_factory, mock_deepface_verification, mock_dedup_config
):
    """Test dedupe_all with a single encoding creates no findings."""
    mock_find_distance, mock_find_threshold, mock_find_confidence = mock_deepface_verification
    mock_find_threshold.return_value = 0.68

    ds = deduplication_set_factory()
    encoding_factory(deduplication_set=ds, filename="file1.jpg", embedding=[0.1] * 512)

    # For a single encoding, the only pair is (0, 0) which is on the diagonal and should be skipped
    mock_find_distance.return_value = np.array([[0.0]])  # Self-distance

    count = dedupe_all(ds, mock_dedup_config)

    assert count == 0
    assert ds.finding_set.count() == 0


@pytest.mark.django_db
def test_dedupe_all_finds_duplicates(
    deduplication_set_factory, encoding_factory, mock_deepface_verification, mock_dedup_config
):
    """Test dedupe_all creates findings for duplicates above threshold."""
    mock_find_distance, mock_find_threshold, mock_find_confidence = mock_deepface_verification
    mock_find_threshold.return_value = 0.68
    mock_find_confidence.return_value = 75.0  # Above threshold

    ds = deduplication_set_factory()
    encoding_factory(deduplication_set=ds, filename="file1.jpg", embedding=[0.1] * 512)
    encoding_factory(deduplication_set=ds, filename="file2.jpg", embedding=[0.11] * 512)

    # Distance matrix: row is chunk, col is all embeddings
    # For 2 encodings with chunk_size=1000, we get one chunk with both
    # Distance matrix should be (2, 2)
    mock_find_distance.return_value = np.array(
        [
            [0.0, 0.3],  # enc1 vs enc1, enc1 vs enc2
            [0.3, 0.0],  # enc2 vs enc1, enc2 vs enc2
        ]
    )

    count = dedupe_all(ds, mock_dedup_config)

    # Should create 1 finding (0,1 pair - upper triangle only)
    assert count == 1
    assert ds.finding_set.count() == 1
    finding = ds.finding_set.first()
    assert finding.score == 0.75  # 75.0 / 100
    assert finding.status_code == Encoding.StatusCode.DEDUPLICATE_SUCCESS


@pytest.mark.django_db
def test_dedupe_all_respects_confidence_threshold(
    deduplication_set_factory, encoding_factory, mock_deepface_verification, mock_dedup_config
):
    """Test dedupe_all skips pairs below confidence threshold."""
    mock_find_distance, mock_find_threshold, mock_find_confidence = mock_deepface_verification
    mock_find_threshold.return_value = 0.68
    mock_find_confidence.return_value = 40.0  # Below threshold of 50.0

    ds = deduplication_set_factory()
    encoding_factory(deduplication_set=ds, filename="file1.jpg", embedding=[0.1] * 512)
    encoding_factory(deduplication_set=ds, filename="file2.jpg", embedding=[0.11] * 512)

    mock_find_distance.return_value = np.array(
        [
            [0.0, 0.5],
            [0.5, 0.0],
        ]
    )

    count = dedupe_all(ds, mock_dedup_config)

    assert count == 0
    assert ds.finding_set.count() == 0


@pytest.mark.django_db
def test_dedupe_all_respects_distance_threshold(
    deduplication_set_factory, encoding_factory, mock_deepface_verification, mock_dedup_config
):
    """Test dedupe_all skips pairs above distance threshold."""
    mock_find_distance, mock_find_threshold, mock_find_confidence = mock_deepface_verification
    mock_find_threshold.return_value = 0.68  # Distance threshold
    mock_find_confidence.return_value = 75.0

    ds = deduplication_set_factory()
    encoding_factory(deduplication_set=ds, filename="file1.jpg", embedding=[0.1] * 512)
    encoding_factory(deduplication_set=ds, filename="file2.jpg", embedding=[0.9] * 512)

    # Distance is 0.8, above threshold of 0.68
    mock_find_distance.return_value = np.array(
        [
            [0.0, 0.8],
            [0.8, 0.0],
        ]
    )

    count = dedupe_all(ds, mock_dedup_config)

    # No findings because distance exceeds threshold
    assert count == 0
    assert ds.finding_set.count() == 0
    # find_confidence should not be called since no pairs passed distance filter
    mock_find_confidence.assert_not_called()


@pytest.mark.django_db
def test_dedupe_all_with_ignored_pairs(
    deduplication_set_factory,
    encoding_factory,
    ignored_filename_pair_factory,
    mock_deepface_verification,
    mock_dedup_config,
):
    """Test dedupe_all respects ignored pairs."""
    mock_find_distance, mock_find_threshold, mock_find_confidence = mock_deepface_verification
    mock_find_threshold.return_value = 0.68
    mock_find_confidence.return_value = 90.0

    ds = deduplication_set_factory()
    encoding_factory(deduplication_set=ds, filename="file1.jpg", embedding=[0.1] * 512)
    encoding_factory(deduplication_set=ds, filename="file2.jpg", embedding=[0.11] * 512)
    ignored_filename_pair_factory(deduplication_set=ds, first="file1.jpg", second="file2.jpg")

    mock_find_distance.return_value = np.array(
        [
            [0.0, 0.2],
            [0.2, 0.0],
        ]
    )

    count = dedupe_all(ds, mock_dedup_config)

    # No findings because the pair is ignored
    assert count == 0
    assert ds.finding_set.count() == 0


@pytest.mark.django_db
def test_dedupe_all_with_approved_encodings(
    deduplication_set_group_factory,
    deduplication_set_factory,
    encoding_factory,
    mock_deepface_verification,
    mock_dedup_config,
):
    """Test dedupe_all includes approved encodings from inactive sets in the same group."""
    mock_find_distance, mock_find_threshold, mock_find_confidence = mock_deepface_verification
    mock_find_threshold.return_value = 0.68
    mock_find_confidence.return_value = 85.0

    group = deduplication_set_group_factory()

    # Create inactive set with approved encodings
    inactive_ds = deduplication_set_factory(group=group, state=DeduplicationSet.State.INACTIVE)
    approved_enc = encoding_factory(
        deduplication_set=inactive_ds,
        filename="approved.jpg",
        embedding=[0.1] * 512,
        state=Encoding.State.APPROVED,
    )

    # Create current deduplication set
    current_ds = deduplication_set_factory(group=group)
    current_enc = encoding_factory(
        deduplication_set=current_ds,
        filename="current.jpg",
        embedding=[0.11] * 512,
    )

    mock_find_distance.return_value = np.array(
        [
            [0.0, 0.2],  # current_enc vs [current, approved]
        ]
    )

    count = dedupe_all(current_ds, mock_dedup_config)

    # Should create 1 finding: current vs approved
    assert count == 1
    assert current_ds.finding_set.count() == 1
    finding = current_ds.finding_set.first()
    assert finding.first_encoding_id == current_enc.id
    assert finding.second_encoding_id == approved_enc.id
    assert finding.score == 0.85


@pytest.mark.django_db
def test_dedupe_all_multiple_encodings(
    deduplication_set_factory, encoding_factory, mock_deepface_verification, mock_dedup_config
):
    """Test dedupe_all with multiple encodings creates correct findings."""
    mock_find_distance, mock_find_threshold, mock_find_confidence = mock_deepface_verification
    mock_find_threshold.return_value = 0.68
    mock_find_confidence.return_value = 80.0

    ds = deduplication_set_factory()
    encoding_factory(deduplication_set=ds, filename="file1.jpg", embedding=[0.1] * 512)
    encoding_factory(deduplication_set=ds, filename="file2.jpg", embedding=[0.11] * 512)
    encoding_factory(deduplication_set=ds, filename="file3.jpg", embedding=[0.12] * 512)

    # Distance matrix where enc1-enc2 and enc2-enc3 are similar, but enc1-enc3 is not
    mock_find_distance.return_value = np.array(
        [
            [0.0, 0.3, 0.9],  # enc1 vs all
            [0.3, 0.0, 0.3],  # enc2 vs all
            [0.9, 0.3, 0.0],  # enc3 vs all
        ]
    )

    count = dedupe_all(ds, mock_dedup_config)

    # Upper triangle pairs below threshold: (0,1)=0.3, (1,2)=0.3
    # (0,2)=0.9 is above threshold
    assert count == 2
    assert ds.finding_set.count() == 2


# --- load_encodings ---------------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_encodings_current_only(deduplication_set_factory, encoding_factory):
    """Test load_encodings loads current encodings into arrays."""
    ds = deduplication_set_factory()
    enc1 = encoding_factory(deduplication_set=ds, filename="file1.jpg", embedding=[0.1] * 512)
    enc2 = encoding_factory(deduplication_set=ds, filename="file2.jpg", embedding=[0.2] * 512)

    current_qs = ds.encoding_set.filter(embedding__isnull=False).order_by("id")
    approved_qs = Encoding.objects.none()

    all_emb, all_ids, all_filenames, n_current = load_encodings(current_qs, approved_qs, 512, 1000)

    assert all_emb.shape == (2, 512)
    assert len(all_ids) == 2
    assert len(all_filenames) == 2
    assert n_current == 2
    assert enc1.id in all_ids
    assert enc2.id in all_ids


@pytest.mark.django_db
def test_load_encodings_with_approved(deduplication_set_group_factory, deduplication_set_factory, encoding_factory):
    """Test load_encodings includes approved encodings from inactive sets."""
    group = deduplication_set_group_factory()

    inactive_ds = deduplication_set_factory(group=group, state=DeduplicationSet.State.INACTIVE)
    approved_enc = encoding_factory(
        deduplication_set=inactive_ds,
        filename="approved.jpg",
        embedding=[0.3] * 512,
        state=Encoding.State.APPROVED,
    )

    current_ds = deduplication_set_factory(group=group)
    current_enc = encoding_factory(
        deduplication_set=current_ds,
        filename="current.jpg",
        embedding=[0.1] * 512,
    )

    current_qs = current_ds.encoding_set.filter(embedding__isnull=False).order_by("id")
    approved_qs = Encoding.objects.filter(
        state=Encoding.State.APPROVED,
        deduplication_set__state=DeduplicationSet.State.INACTIVE,
        deduplication_set__group=group,
        embedding__isnull=False,
    ).order_by("id")

    all_emb, all_ids, all_filenames, n_current = load_encodings(current_qs, approved_qs, 512, 1000)

    assert all_emb.shape == (2, 512)
    assert n_current == 1
    assert all_ids[0] == current_enc.id
    assert all_ids[1] == approved_enc.id
    assert all_filenames[0] == "current.jpg"
    assert all_filenames[1] == "approved.jpg"


# --- find_duplicate_pairs ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_find_duplicate_pairs_returns_matches(mock_deepface_verification, mock_dedup_config):
    """Test find_duplicate_pairs returns matching pairs above confidence threshold."""
    mock_find_distance, mock_find_threshold, mock_find_confidence = mock_deepface_verification
    mock_find_threshold.return_value = 0.68
    mock_find_confidence.return_value = 75.0

    all_emb = np.array([[0.1] * 512, [0.2] * 512], dtype=np.float32)
    all_ids = [1, 2]
    all_filenames = ["file1.jpg", "file2.jpg"]

    mock_find_distance.return_value = np.array([[0.0, 0.3], [0.3, 0.0]])

    duplicates = find_duplicate_pairs(
        all_emb, all_ids, all_filenames, n_current=2, ignored_pairs=set(), config=mock_dedup_config, chunk_size=1000
    )

    assert len(duplicates) == 1
    assert duplicates[0] == (1, 2, 75.0)


@pytest.mark.django_db
def test_find_duplicate_pairs_skips_ignored(mock_deepface_verification, mock_dedup_config):
    """Test find_duplicate_pairs skips ignored pairs."""
    mock_find_distance, mock_find_threshold, mock_find_confidence = mock_deepface_verification
    mock_find_threshold.return_value = 0.68
    mock_find_confidence.return_value = 75.0

    all_emb = np.array([[0.1] * 512, [0.2] * 512], dtype=np.float32)
    all_ids = [1, 2]
    all_filenames = ["file1.jpg", "file2.jpg"]
    ignored_pairs = {frozenset(["file1.jpg", "file2.jpg"])}

    mock_find_distance.return_value = np.array([[0.0, 0.3], [0.3, 0.0]])

    duplicates = find_duplicate_pairs(
        all_emb,
        all_ids,
        all_filenames,
        n_current=2,
        ignored_pairs=ignored_pairs,
        config=mock_dedup_config,
        chunk_size=1000,
    )

    assert len(duplicates) == 0


@pytest.mark.django_db
def test_find_duplicate_pairs_skips_below_confidence(mock_deepface_verification, mock_dedup_config):
    """Test find_duplicate_pairs skips pairs below confidence threshold."""
    mock_find_distance, mock_find_threshold, mock_find_confidence = mock_deepface_verification
    mock_find_threshold.return_value = 0.68
    mock_find_confidence.return_value = 30.0  # Below 50.0 threshold

    all_emb = np.array([[0.1] * 512, [0.2] * 512], dtype=np.float32)
    all_ids = [1, 2]
    all_filenames = ["file1.jpg", "file2.jpg"]

    mock_find_distance.return_value = np.array([[0.0, 0.3], [0.3, 0.0]])

    duplicates = find_duplicate_pairs(
        all_emb, all_ids, all_filenames, n_current=2, ignored_pairs=set(), config=mock_dedup_config, chunk_size=1000
    )

    assert len(duplicates) == 0
