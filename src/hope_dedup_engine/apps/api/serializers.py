from typing import Any

from rest_framework import serializers

from hope_dedup_engine.apps.api.models import DeduplicationSet
from hope_dedup_engine.apps.api.models.deduplication import (
    Config,
    Duplicate,
    IgnoredKeyPair,
    Image,
)

CONFIG = "config"


class ConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config
        exclude = ("id",)


class DeduplicationSetSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source="get_state_value_display", read_only=True)
    config = ConfigSerializer(required=False)

    class Meta:
        model = DeduplicationSet
        exclude = ("deleted", "state_value")
        read_only_fields = (
            "external_system",
            "created_at",
            "created_by",
            "deleted",
            "updated_at",
            "updated_by",
        )

    def create(self, validated_data) -> DeduplicationSet:
        config_data = validated_data.get(CONFIG) and validated_data.pop(CONFIG)
        config = Config.objects.create(**config_data) if config_data else None
        return DeduplicationSet.objects.create(config=config, **validated_data)


class CreateConfigSerializer(ConfigSerializer):
    pass


class CreateDeduplicationSetSerializer(serializers.ModelSerializer):
    config = CreateConfigSerializer(required=False)

    class Meta:
        model = DeduplicationSet
        fields = ("config", "reference_pk", "notification_url")


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
