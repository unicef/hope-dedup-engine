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


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = "__all__"
        read_only_fields = "created_by", "created_at"


class EntrySerializer(serializers.Serializer):
    reference_pk = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()

    def __init__(self, prefix: str, *args: Any, **kwargs: Any) -> None:
        self._prefix = prefix
        super().__init__(*args, **kwargs)

    def get_reference_pk(self, duplicate: Duplicate) -> int:
        return getattr(duplicate, f"{self._prefix}_reference_pk")

    def get_filename(self, duplicate: Duplicate) -> str:
        return getattr(duplicate, f"{self._prefix}_filename")


class DuplicateSerializer(serializers.Serializer):
    first = EntrySerializer(prefix="first", source="*")
    second = EntrySerializer(prefix="second", source="*")


class IgnoredKeyPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = IgnoredKeyPair
        fields = "__all__"
