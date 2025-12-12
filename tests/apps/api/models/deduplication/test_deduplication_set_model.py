import pytest
from collections.abc import Callable
from typing import Literal, cast


from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding
from testutils.factories.api import DeduplicationSetFactory, EncodingFactory


@pytest.fixture
def ds() -> DeduplicationSet:
    return DeduplicationSetFactory()


ErrorTrait = Literal["face_detect_error", "system_error"]


@pytest.fixture
def make_images() -> Callable[[DeduplicationSet, list[str]], list[Encoding]]:
    def make(
        ds: DeduplicationSet,
        filenames: list[str],
        filenames_with_embeddings: set[str] | None = None,
        filenames_with_errors: dict[str, ErrorTrait] | None = None,
    ) -> list[Encoding]:
        if filenames_with_embeddings is None:
            filenames_with_embeddings = set()
        if filenames_with_errors is None:
            filenames_with_errors = {}

        return [
            cast(
                "Encoding",
                EncodingFactory(
                    deduplication_set=ds,
                    filename=filename,
                    **{"embedding": None} if filename not in filenames_with_embeddings else {},
                    **{filenames_with_errors[filename]: True} if filename in filenames_with_errors else {},
                ),
            )
            for filename in filenames
        ]

    return make


@pytest.fixture
def make_findings(ds):
    def make(items: list[tuple[str, str, float]] | None):
        for fpk, spk, score in items or []:
            ds.finding_set.create(
                first_reference_pk=fpk,
                second_reference_pk=spk,
                score=score,
            )

    return make


@pytest.mark.parametrize(
    ("filenames", "filenames_with_embeddings", "expected"),
    [
        pytest.param(["a.jpg", "b.jpg"], [], ["a.jpg", "b.jpg"], id="all_missing"),
        pytest.param(["a.jpg", "b.jpg", "c.jpg"], ["a.jpg"], ["b.jpg", "c.jpg"], id="partial"),
        pytest.param(["a.jpg"], ["a.jpg"], [], id="all_encoded"),
        pytest.param([], [], [], id="empty"),
    ],
)
def test_encodings_without_embeddings(
    ds: DeduplicationSet,
    make_images: Callable,
    filenames: list[str],
    filenames_with_embeddings: list[str],
    expected: list[str],
):
    make_images(ds, filenames, filenames_with_embeddings)
    assert set(ds.encodings_without_embeddings().values_list("filename", flat=True)) == set(expected)


def test_encodings_without_embeddings_reuses_global_encoding(
    ds: DeduplicationSet,
    make_images: Callable,
):
    make_images(ds, ["shared.jpg", "unique.jpg"], ["shared.jpg"])
    assert list(ds.encodings_without_embeddings().values_list("filename", flat=True)) == ["unique.jpg"]


def test_encodings_without_embeddings_includes_missing_and_system_excludes_face(
    ds: DeduplicationSet, make_images: Callable
):
    make_images(
        ds,
        ["with_embedding.jpg", "face_err.jpg", "sys_err.jpg", "missing_filename.jpg"],
        ["with_embedding.jpg"],
        {
            "face_err.jpg": "face_detect_error",
            "sys_err.jpg": "system_error",
        },
    )
    assert set(ds.encodings_without_embeddings().values_list("filename", flat=True)) == {
        "sys_err.jpg",
        "missing_filename.jpg",
    }
