from hope_dedup_engine.apps.api.serializers import CreateEncodingSerializer


def test_filename_field_accepts_plain_filename() -> None:
    serializer = CreateEncodingSerializer()
    assert serializer.fields["filename"].run_validation("hope/image.jpg") == "hope/image.jpg"
