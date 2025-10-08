import pytest
from collections.abc import Callable
from typing import Literal
from unittest.mock import call

from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.models import DeduplicationSet, Image, Encoding
from testutils.factories.api import DeduplicationSetFactory, EncodingFactory, ImageFactory


@pytest.fixture
def ds() -> DeduplicationSet:
    return DeduplicationSetFactory()


@pytest.fixture
def make_images() -> Callable[[DeduplicationSet, list[str]], list[Image]]:
    def _make(ds: DeduplicationSet, filenames: list[str]) -> list[Image]:
        return [ImageFactory(deduplication_set=ds, filename=fn) for fn in filenames]

    return _make


@pytest.fixture
def make_encodings() -> Callable[[list[str]], list[Encoding]]:
    def _make(filenames: list[str]) -> list[Encoding]:
        return [EncodingFactory(filename=fn) for fn in filenames]

    return _make


ErrorTrait = Literal["face_detect_error", "system_error"]


@pytest.fixture
def make_encodings_error() -> Callable[[list[tuple[str, ErrorTrait]] | None], None]:
    def _make(pairs: list[tuple[str, ErrorTrait]] | None) -> None:
        for fn, trait in pairs or []:
            EncodingFactory(filename=fn, **{trait: True})

    return _make


@pytest.fixture
def make_findings(ds):
    def _make(items: list[tuple[str, str, float]] | None):
        for fpk, spk, score in items or []:
            ds.finding_set.create(
                first_reference_pk=fpk,
                second_reference_pk=spk,
                score=score,
            )

    return _make


def test_update_encodings(mocker: MockerFixture) -> None:
    encoding_model_mock = mocker.patch("hope_dedup_engine.apps.api.models.deduplication.Encoding")
    model = DeduplicationSet()

    encodings = {"c": [2.0], "b": 1, "a": [0.0]}  # int = status_code, list = embedding
    model.update_encodings(encodings)

    encoding_model_mock.objects.bulk_create.assert_called_once_with(
        [encoding_model_mock.return_value] * len(encodings),
        update_conflicts=True,
        update_fields=["embedding", "status_code"],
        unique_fields=["filename"],
    )
    encoding_model_mock.assert_has_calls(
        [
            call(filename="a", embedding=[0.0], status_code=None),
            call(filename="b", embedding=None, status_code=1),
            call(filename="c", embedding=[2.0], status_code=None),
        ]
    )


@pytest.mark.parametrize(
    ("filenames", "filenames_with_encodings", "expected"),
    [
        (["a.jpg", "b.jpg"], [], ["a.jpg", "b.jpg"]),
        (["a.jpg", "b.jpg", "c.jpg"], ["a.jpg"], ["b.jpg", "c.jpg"]),
        (["a.jpg"], ["a.jpg"], []),
        ([], [], []),
    ],
    ids=["all_missing", "partial", "all_encoded", "empty"],
)
def test_filenames_without_encodings(
    ds: DeduplicationSet,
    make_images: Callable,
    make_encodings: Callable,
    filenames: list[str],
    filenames_with_encodings: list[str],
    expected: list[str],
):
    make_images(ds, filenames)
    make_encodings(filenames_with_encodings)
    assert set(ds.filenames_without_encodings()) == set(expected)


def test_filenames_without_encodings_reuses_global_encoding(
    ds: DeduplicationSet,
    make_images: Callable,
    make_encodings: Callable,
):
    make_images(ds, ["shared.jpg", "unique.jpg"])
    make_encodings(["shared.jpg"])
    assert list(ds.filenames_without_encodings()) == ["unique.jpg"]


def test_filenames_without_encodings_includes_missing_and_system_excludes_face(
    ds: DeduplicationSet,
    make_images: Callable,
    make_encodings: Callable,
    make_encodings_error: Callable,
):
    make_images(ds, ["with_embedding.jpg", "face_err.jpg", "sys_err.jpg", "missing_filename.jpg"])
    make_encodings(["with_embedding.jpg"])
    make_encodings_error(
        [
            ("face_err.jpg", "face_detect_error"),
            ("sys_err.jpg", "system_error"),
        ]
    )
    assert set(ds.filenames_without_encodings()) == {"sys_err.jpg", "missing_filename.jpg"}


def test_get_findings(ds: DeduplicationSet, make_findings: Callable) -> None:
    make_findings([("A", "B", 0.95), ("X", "Y", 0.80)])
    got = {(a, b, round(float(s), 5)) for a, b, s in ds.get_findings()}
    assert got == {("A", "B", 0.95), ("X", "Y", 0.8)}
