from unittest.mock import call

from pytest_mock import MockerFixture

from hope_dedup_engine.apps.api.models import DeduplicationSet


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
