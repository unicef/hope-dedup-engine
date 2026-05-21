import base64
import mimetypes
from itertools import filterfalse
from typing import Any

from django.core.files.base import ContentFile
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models import (
    DeduplicationSet,
    Finding,
    Encoding,
)
from hope_dedup_engine.apps.api.utils.image import encoding_image_key
from hope_dedup_engine.apps.api.utils.data_url import parse_data_url


class DeduplicationSetSerializer(serializers.ModelSerializer):
    reference_pk = serializers.CharField(source="group.reference_pk")
    name = serializers.CharField(source="group.name", read_only=True, allow_null=True)
    state = serializers.CharField(source="get_state_display", read_only=True)
    findings_count = serializers.IntegerField()

    def to_representation(self, instance: DeduplicationSet) -> dict[str, Any]:
        if not hasattr(instance, "findings_count"):
            instance.findings_count = instance.finding_set.count()

        return super().to_representation(instance)

    class Meta:
        model = DeduplicationSet
        fields = ("id", "reference_pk", "name", "state", "findings_count", "created_at", "updated_at")


class CreateDeduplicationSetSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(
        required=False,
        validators=[UniqueValidator(queryset=DeduplicationSet.objects.all())],
    )
    reference_pk = serializers.CharField(source="group.reference_pk")
    name = serializers.CharField(source="group.name", required=False, allow_null=True, allow_blank=True)
    state = serializers.CharField(source="get_state_display", read_only=True)

    class Meta:
        model = DeduplicationSet
        fields = ("id", "reference_pk", "name", "notification_url", "notify", "state")


class EncodingSerializer(serializers.ModelSerializer):
    deduplication_set = DeduplicationSetSerializer(read_only=True)
    filename = serializers.CharField(source="filename.name", read_only=True)

    class Meta:
        model = Encoding
        fields = (
            "id",
            "deduplication_set",
            "reference_pk",
            "filename",
            "created_by",
            "created_at",
        )
        read_only_fields = "created_by", "created_at"


def is_deduplication_set_reference_pk_constraint(constraint) -> bool:
    fields, *_ = constraint
    return fields == ("deduplication_set", "reference_pk")


class CreateEncodingSerializer(serializers.ModelSerializer):
    deduplication_set = serializers.PrimaryKeyRelatedField(
        queryset=DeduplicationSet.objects.all(),
        default=serializers.CreateOnlyDefault(
            lambda serializer_field: serializer_field.context["view"].get_parent_object()
        ),
        write_only=True,
    )
    filename = serializers.CharField(write_only=True)

    class Meta:
        model = Encoding
        fields = ("reference_pk", "filename", "deduplication_set")

    def get_unique_together_constraints(self, model):
        # Here the constraint for deduplication set + reference_pk is disabled
        # to allow the Image model to update filename if an image object with
        # the same reference_pk is added to the deduplication set
        yield from filterfalse(
            is_deduplication_set_reference_pk_constraint, super().get_unique_together_constraints(model)
        )

    def validate_filename(self, value: str) -> str:
        parsed = parse_data_url(value)
        if not parsed or parsed.encoding != "base64" or not parsed.content:
            raise serializers.ValidationError("filename must be a base64 data URL (data:<mimetype>;base64,<payload>).")
        try:
            base64.b64decode(parsed.content, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise serializers.ValidationError("filename payload is not valid base64.") from exc
        return value

    def create(self, validated_data: dict[str, Any]) -> Encoding:
        deduplication_set: DeduplicationSet = validated_data["deduplication_set"]
        reference_pk: str = validated_data["reference_pk"]
        data_url: str = validated_data["filename"]

        parsed = parse_data_url(data_url)
        # validate_filename guarantees parsed and base64 encoding
        payload = base64.b64decode(parsed.content)
        ext = mimetypes.guess_extension(parsed.mimetype or "") or ".bin"
        basename = f"{reference_pk}{ext}"

        target_key = encoding_image_key(
            deduplication_set.group.reference_pk,
            deduplication_set.id,
            basename,
        )
        storage = Encoding.filename.field.storage
        if storage.exists(target_key):
            storage.delete(target_key)

        validated_data["filename"] = ContentFile(payload, name=basename)
        return super().create(validated_data)


class EntrySerializer(serializers.Serializer):
    reference_pk = serializers.SerializerMethodField()

    def __init__(self, prefix: str, *args: Any, **kwargs: Any) -> None:
        self._prefix = prefix
        super().__init__(*args, **kwargs)

    def get_reference_pk(self, duplicate: Finding) -> int:
        encoding = getattr(duplicate, f"{self._prefix}_encoding", None)
        return encoding.reference_pk if encoding else ""


class DuplicateSerializer(serializers.ModelSerializer):
    first = EntrySerializer(prefix="first", source="*")
    second = EntrySerializer(prefix="second", source="*")

    class Meta:
        model = Finding
        fields = "first", "second", "score", "status_code", "config", "updated_at"


class EmptySerializer(serializers.Serializer):
    pass


class GroupStatusSerializer(serializers.Serializer):
    can_create = serializers.BooleanField()


class GroupSettingsSerializer(serializers.Serializer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for f in DeduplicationSetConfig.setting_fields(api=True):
            meta = f.metadata
            self.fields[f.name] = serializers.FloatField(
                min_value=meta["min_value"],
                max_value=meta["max_value"],
                required=False,
                help_text=meta["help_text"],
            )
