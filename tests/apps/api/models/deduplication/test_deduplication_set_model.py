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


@pytest.fixture
def ds_with_pair_and_single_finding(ds, encoding_factory, finding_factory):
    e1, e2, e3 = (encoding_factory(deduplication_set=ds) for _ in range(3))
    pair_finding = finding_factory(deduplication_set=ds, first_encoding=e1, second_encoding=e2)
    finding_factory(deduplication_set=ds, first_encoding=e3, second_encoding=None)
    return ds, pair_finding


@pytest.fixture
def ds_with_single_encoding_finding(ds, encoding_factory, finding_factory):
    e1 = encoding_factory(deduplication_set=ds)
    finding_factory(deduplication_set=ds, first_encoding=e1, second_encoding=None)
    return ds


@pytest.fixture
def ds_with_mixed_embeddings(ds, encoding_factory):
    encoding_factory(deduplication_set=ds, embedding=[0.1, 0.2], embedding_status_code=None)
    encoding_factory(deduplication_set=ds, embedding=None, embedding_status_code=200)
    return ds


@pytest.fixture
def ds_with_findings(ds, finding_factory):
    finding_factory(deduplication_set=ds)
    finding_factory(deduplication_set=ds)
    return ds


@pytest.fixture
def ds_with_encodings(ds, encoding_factory):
    encoding_factory(deduplication_set=ds)
    encoding_factory(deduplication_set=ds)
    return ds


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


def test_duplicate_findings_returns_only_findings_with_second_encoding(ds_with_pair_and_single_finding):
    ds, pair_finding = ds_with_pair_and_single_finding

    assert list(ds.duplicate_findings()) == [pair_finding]


def test_duplicate_findings_returns_empty_when_no_findings(ds):
    assert ds.duplicate_findings().count() == 0


def test_duplicate_findings_returns_empty_when_only_single_encoding_findings(ds_with_single_encoding_finding):
    assert ds_with_single_encoding_finding.duplicate_findings().count() == 0


def test_clear_embeddings_data_clears_embeddings_and_status_codes(ds_with_mixed_embeddings):
    ds_with_mixed_embeddings.clear_embeddings_data()

    for enc in ds_with_mixed_embeddings.encoding_set.all():
        assert enc.embedding is None
        assert enc.embedding_status_code is None


def test_clear_embeddings_data_deletes_all_findings(ds_with_findings):
    assert ds_with_findings.finding_set.count() == 2

    ds_with_findings.clear_embeddings_data()

    assert ds_with_findings.finding_set.count() == 0


def test_clear_embeddings_data_preserves_encodings(ds_with_encodings):
    ds_with_encodings.clear_embeddings_data()

    assert ds_with_encodings.encoding_set.count() == 2


def test_clear_embeddings_data_no_op_on_empty_set(ds):
    ds.clear_embeddings_data()

    assert ds.encoding_set.count() == 0
    assert ds.finding_set.count() == 0
