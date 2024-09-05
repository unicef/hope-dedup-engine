from typing import Any

from rest_framework import serializers

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import (
    Duplicate,
    IgnoredKeyPair,
    Image,
)


class DeduplicationSetSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source="get_state_display", read_only=True)

    class Meta:
        model = DeduplicationSet
        exclude = ("deleted",)
        read_only_fields = (
            "external_system",
            "created_at",
            "created_by",
            "deleted",
            "updated_at",
            "updated_by",
        )


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

    def __init__(self, prefix: str, *args: Any, **kwargs: Any) -> None:
        self._prefix = prefix
        super().__init__(*args, **kwargs)

    def get_reference_pk(self, duplicate: Duplicate) -> int:
        return getattr(duplicate, f"{self._prefix}_reference_pk")


class DuplicateSerializer(serializers.ModelSerializer):
    first = EntrySerializer(prefix="first", source="*")
    second = EntrySerializer(prefix="second", source="*")

    class Meta:
        model = Duplicate
        fields = "first", "second", "score"


class IgnoredKeyPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = IgnoredKeyPair
        fields = "__all__"


class CreateIgnoredKeyPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = IgnoredKeyPair
        fields = ("first_reference_pk", "second_reference_pk")


class EmptySerializer(serializers.Serializer):
    pass
