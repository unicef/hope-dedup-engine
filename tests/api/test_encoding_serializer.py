import pytest
from rest_framework.exceptions import ValidationError

from hope_dedup_engine.apps.api.serializers import CreateEncodingSerializer


def test_validate_filename_rejects_non_data_url() -> None:
    serializer = CreateEncodingSerializer()

    with pytest.raises(ValidationError, match="filename must be a base64 data URL"):
        serializer.validate_filename("not-a-data-url")


def test_validate_filename_rejects_invalid_base64() -> None:
    serializer = CreateEncodingSerializer()

    with pytest.raises(ValidationError, match="filename payload is not valid base64"):
        serializer.validate_filename("data:image/jpeg;base64,!!!not-valid!!!")
