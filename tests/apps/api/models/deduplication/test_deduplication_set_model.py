import pytest
from unittest.mock import call

from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.models.deduplication import DeduplicationSet
from testutils.factories.api import DeduplicationSetFactory, EncodingFactory, ImageFactory


@pytest.fixture
def ds():
    return DeduplicationSetFactory()


@pytest.fixture
def make_images():
    def _make(ds, filenames):
        return [ImageFactory(deduplication_set=ds, filename=fn) for fn in filenames]

    return _make


@pytest.fixture
def make_encodings():
    def _make(ds, filenames):
        return [EncodingFactory(deduplication_set=ds, filename=fn) for fn in filenames]

    return _make


def test_update_encodings(mocker: MockerFixture) -> None:
    encoding_model_mock = mocker.patch("hope_dedup_engine.apps.api.models.deduplication.Encoding")
    model = DeduplicationSet()
    model.update_encodings(encodings := {"c": [2], "b": [1], "a": [0]})
    encoding_model_mock.objects.bulk_create.assert_called_once_with(
        [encoding_model_mock.return_value] * len(encodings),
        update_conflicts=True,
        update_fields=["data"],
        unique_fields=["deduplication_set", "filename"],
    )
    encoding_model_mock.assert_has_calls(
        [call(deduplication_set=model, filename=key, data=encodings[key]) for key in sorted(encodings.keys())]
    )


@pytest.mark.parametrize(
    ("filenames", "filenames_with_encodings", "expected"),
    [
        (["a.jpg", "b.jpg"], [], ["a.jpg", "b.jpg"]),
        (["a.jpg", "b.jpg", "c.jpg"], ["a.jpg"], ["b.jpg", "c.jpg"]),
        (["a.jpg"], ["a.jpg"], []),
        ([], [], []),
        (["z.jpg", "a.jpg", "m.jpg"], [], ["a.jpg", "m.jpg", "z.jpg"]),
    ],
    ids=["all_missing", "partial", "all_encoded", "empty", "ordered"],
)
def test_filenames_without_encodings(ds, make_images, make_encodings, filenames, filenames_with_encodings, expected):
    make_images(ds, filenames)
    make_encodings(ds, filenames_with_encodings)

    assert list(ds.filenames_without_encodings()) == expected


def test_filenames_without_encodings_cross_ds(ds, make_images, make_encodings):
    other_ds = DeduplicationSetFactory()
    make_images(ds, ["shared.jpg", "unique.jpg"])
    make_encodings(other_ds, ["shared.jpg"])

    assert list(ds.filenames_without_encodings()) == ["unique.jpg"]
