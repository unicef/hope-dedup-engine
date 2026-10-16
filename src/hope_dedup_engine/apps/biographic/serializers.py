from typing import Any, Final

from rest_framework import serializers

from hope_dedup_engine.apps.api.models.deduplication import REFERENCE_PK_LENGTH
from hope_dedup_engine.apps.biographic.config import BiographicConfig
from hope_dedup_engine.apps.biographic.models import NOTIFICATION_URL_LENGTH, BiographicFinding, BiographicSet
from hope_dedup_engine.apps.biographic.schemas import PAYLOAD_FIELDS

BIRTH_DATE_FIELD: Final[str] = "birth_date"

MAX_RECORDS_PER_BATCH: Final[int] = 10_000

DUPLICATE_IN_BATCH: Final[str] = "Duplicate reference_pk in this batch."


class IsoDateField(serializers.DateField):
    """Validate an ISO 8601 date but keep it a string: the payload is stored as JSON."""

    def to_internal_value(self, value: Any) -> str:  # type: ignore[override]
        return super().to_internal_value(value).isoformat()


class BiographicPayloadSerializer(serializers.Serializer):
    """One person's scoreable fields, generated from `schemas.PAYLOAD_FIELDS`.

    Keys outside that list are dropped rather than rejected: a client may hold more
    about a person than we score. Values are stored as sent - no trimming - so a
    payload reads back exactly as it was posted.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for name in PAYLOAD_FIELDS:
            if name == BIRTH_DATE_FIELD:
                self.fields[name] = IsoDateField(required=False, allow_null=True)
            else:
                self.fields[name] = serializers.CharField(
                    required=False, allow_null=True, allow_blank=True, trim_whitespace=False
                )


class BiographicRecordSerializer(serializers.Serializer):
    reference_pk = serializers.CharField(max_length=REFERENCE_PK_LENGTH, trim_whitespace=False)
    payload = BiographicPayloadSerializer()


class RecordsBatchSerializer(serializers.Serializer):
    """A batch of people to add to a pending set.

    Re-sending a `reference_pk` already in the set replaces it, so a client that
    retries a batch after a timeout cannot create duplicates.
    """

    records = BiographicRecordSerializer(many=True, allow_empty=False, max_length=MAX_RECORDS_PER_BATCH)

    def validate_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Keyed by position, the shape DRF itself uses for errors in a list.
        seen: set[str] = set()
        errors: dict[int, dict[str, list[str]]] = {}
        for position, record in enumerate(records):
            if record["reference_pk"] in seen:
                errors[position] = {"reference_pk": [DUPLICATE_IN_BATCH]}
            seen.add(record["reference_pk"])
        if errors:
            raise serializers.ValidationError(errors)
        return records


class RecordsBatchResultSerializer(serializers.Serializer):
    received = serializers.IntegerField(help_text="Records in this batch, new or replaced.")
    records_count = serializers.IntegerField(help_text="Records in the set after this batch.")


class BiographicSetCreateSerializer(serializers.ModelSerializer):
    """What a client may set when creating a set. Both are optional."""

    notification_url = serializers.URLField(
        max_length=NOTIFICATION_URL_LENGTH,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Pinged with a GET on every state change a run makes.",
    )

    class Meta:
        model = BiographicSet
        fields = ("notification_url", "notify")
        extra_kwargs = {"notify": {"required": False}}


class BiographicSetSerializer(serializers.ModelSerializer):
    dataset_id = serializers.IntegerField(source="pk", read_only=True)
    status = serializers.CharField(source="state", read_only=True)
    records_count = serializers.IntegerField(read_only=True)
    batch_duplicates = serializers.IntegerField(
        read_only=True, help_text="Records with at least one duplicate inside this set."
    )
    population_duplicates = serializers.IntegerField(
        read_only=True, help_text="Records with at least one duplicate in the program's approved population."
    )

    class Meta:
        model = BiographicSet
        fields = (
            "dataset_id",
            "status",
            "error",
            "records_count",
            "batch_duplicates",
            "population_duplicates",
            "notification_url",
            "notify",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class BiographicPairSerializer(serializers.ModelSerializer):
    reference_pk = serializers.CharField(source="record.reference_pk", read_only=True)

    class Meta:
        model = BiographicFinding
        fields = (
            "reference_pk",
            "matched_reference_pk",
            "scope",
            "score",
            "proximity_to_score",
            "matched_full_name",
            "matched_birth_date",
        )
        read_only_fields = fields


class ProcessOverridesSerializer(serializers.Serializer):
    """Optional per-run overrides of the group's settings.

    Unlike a payload, an unknown key here is an error: a misspelt threshold that is
    silently ignored would run the whole dataset with the wrong one.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for f in BiographicConfig.setting_fields():
            meta = f.metadata
            field_class = serializers.FloatField if meta["kind"] is float else serializers.IntegerField
            self.fields[f.name] = field_class(required=False, min_value=meta["min_value"], help_text=meta["help_text"])

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError(dict.fromkeys(unknown, ["Unknown setting."]))
        return attrs
