from itertools import filterfalse
from typing import Any

from rest_framework import serializers

from hope_dedup_engine.apps.api.models import (
    DeduplicationSet,
    Finding,
    IgnoredFilenamePair,
    IgnoredReferencePkPair,
    Encoding,
)


class DeduplicationSetSerializer(serializers.ModelSerializer):
    reference_pk = serializers.CharField(source="group.reference_pk")
    state = serializers.CharField(source="get_state_display", read_only=True)

    class Meta:
        model = DeduplicationSet
        fields = "__all__"
        read_only_fields = (
            "group",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        )


class CreateDeduplicationSetSerializer(serializers.ModelSerializer):
    reference_pk = serializers.CharField(source="group.reference_pk")
    state = serializers.CharField(source="get_state_display", read_only=True)

    class Meta:
        model = DeduplicationSet
        fields = ("reference_pk", "notification_url", "notify", "state")


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
        fields = "first", "second", "score", "status_code", "updated_at"


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


class EncodingReferencePks(serializers.Serializer):
    reference_pks = serializers.ListField(child=serializers.CharField(), required=False)
