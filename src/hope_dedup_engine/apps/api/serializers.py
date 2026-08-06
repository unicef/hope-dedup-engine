from itertools import filterfalse
from typing import Any

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.deduplication.export import EXPORT_FORMAT_NPY, EXPORT_FORMATS
from hope_dedup_engine.apps.api.models import (
    DeduplicationSet,
    Finding,
    Encoding,
)


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


class CreateEncodingsExportSerializer(serializers.Serializer):
    reference_pk = serializers.SlugField(
        max_length=100,
        help_text="External reference (e.g. country office slug) used in the export blob key.",
    )
    deduplication_set_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        help_text="Deduplication sets whose encodings are bundled into the zip.",
    )
    format = serializers.ChoiceField(
        choices=EXPORT_FORMATS,
        default=EXPORT_FORMAT_NPY,
        help_text="Zip payload format: 'npy' (single float32 matrix + index, compact) "
        "or 'jsonl' (self-describing lines with embeddings inline).",
    )


class EncodingsExportStatusSerializer(serializers.Serializer):
    key = serializers.CharField(help_text="Export blob key (opaque; returned when the export was requested).")
    state = serializers.ChoiceField(choices=("pending", "ready", "failed"))
    url = serializers.CharField(required=False, help_text="Signed download URL (only when state is ready).")
    expires_at = serializers.DateTimeField(required=False, help_text="Signed URL expiry (only when state is ready).")
    error = serializers.CharField(required=False, help_text="Failure message (only when state is failed).")


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
