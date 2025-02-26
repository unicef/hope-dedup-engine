from typing import Any

from rest_framework import serializers

from hope_dedup_engine.apps.api.models import (
    Config,
    DeduplicationSet,
    Finding,
    IgnoredFilenamePair,
    IgnoredReferencePkPair,
    Image,
)


class ConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config
        exclude = ("id",)


class DeduplicationSetSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source="get_state_display", read_only=True)
    config = ConfigSerializer(required=False)

    class Meta:
        model = DeduplicationSet
        exclude = ("deleted", "encodings")
        read_only_fields = (
            "external_system",
            "created_at",
            "created_by",
            "deleted",
            "updated_at",
            "updated_by",
        )


class CreateConfigSerializer(ConfigSerializer):
    pass


class CreateDeduplicationSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeduplicationSet
        fields = ("reference_pk", "notification_url")


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = (
            "id",
            "deduplication_set",
            "reference_pk",
            "filename",
            "created_by",
            "created_at",
        )
        read_only_fields = "created_by", "created_at"


class CreateImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = (
            "reference_pk",
            "filename",
        )


class EntrySerializer(serializers.Serializer):
    reference_pk = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()

    def __init__(self, prefix: str, *args: Any, **kwargs: Any) -> None:
        self._prefix = prefix
        super().__init__(*args, **kwargs)

    def get_reference_pk(self, duplicate: Finding) -> int:
        return getattr(duplicate, f"{self._prefix}_reference_pk")

    def get_filename(self, duplicate: Finding) -> str:
        return getattr(duplicate, f"{self._prefix}_filename")


class DuplicateSerializer(serializers.ModelSerializer):
    first = EntrySerializer(prefix="first", source="*")
    second = EntrySerializer(prefix="second", source="*")

    class Meta:
        model = Finding
        fields = "first", "second", "score", "status_code"


CREATE_PAIR_FIELDS = "first", "second"
PAIR_FIELDS = ("id", "deduplication_set") + CREATE_PAIR_FIELDS


class IgnoredReferencePkPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = IgnoredReferencePkPair
        fields = PAIR_FIELDS


class CreateIgnoredReferencePkPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = IgnoredReferencePkPair
        fields = CREATE_PAIR_FIELDS


class IgnoredFilenamePairSerializer(serializers.ModelSerializer):
    class Meta:
        model = IgnoredFilenamePair
        fields = PAIR_FIELDS


class CreateIgnoredFilenamePairSerializer(serializers.ModelSerializer):
    class Meta:
        model = IgnoredFilenamePair
        fields = CREATE_PAIR_FIELDS


class EmptySerializer(serializers.Serializer):
    pass
