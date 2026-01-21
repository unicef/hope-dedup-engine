from itertools import filterfalse
from typing import Any

from django_celery_boost.models import CeleryTaskModel
from rest_framework import serializers

from hope_dedup_engine.apps.api.models import (
    DeduplicationSet,
    Finding,
    IgnoredFilenamePair,
    IgnoredReferencePkPair,
    Encoding,
    MainJob,
)
from hope_dedup_engine.apps.api.models.jobs import (
    EncodeChunkJob,
    DeduplicateDatasetJob,
    DedupeChunkJob,
    CallbackFindingsJob,
)


class DeduplicationSetSerializer(serializers.ModelSerializer):
    reference_pk = serializers.CharField(source="group.reference_pk")
    name = serializers.CharField(source="group.name", read_only=True, allow_null=True)
    state = serializers.CharField(source="get_state_display", read_only=True)
    status = serializers.SerializerMethodField()
    duplicates_found = serializers.IntegerField()

    def to_representation(self, instance: DeduplicationSet) -> dict[str, Any]:
        if not hasattr(instance, "duplicates_found"):
            instance.duplicates_found = instance.finding_set.count()

        return super().to_representation(instance)

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

    def get_status(self, deduplication_set: DeduplicationSet) -> str:
        # EncodeChunkJob and DeduplicateDatasetJob are created inside the
        # DedupJob. DedupeChunkJob and CallbackFindingsJob are created inside
        # the DeduplicateDatasetJob. So we always have the next job object
        # created before the current job is finished

        job_managers = (
            MainJob.objects.filter(deduplication_set=deduplication_set),
            EncodeChunkJob.objects.filter(deduplication_set=deduplication_set),
            DeduplicateDatasetJob.objects.filter(deduplication_set=deduplication_set),
            DedupeChunkJob.objects.filter(deduplication_set=deduplication_set),
            CallbackFindingsJob.objects.filter(deduplication_set=deduplication_set),
        )

        first_task = True

        for job_manager in job_managers:
            job = job_manager.order_by("-id").first()

            if job is None:
                # we only get here if no job was scheduled or the previous task
                # finished without being able to create the next task, which
                # means some other failure
                return CeleryTaskModel.NOT_SCHEDULED

            if (result := job.async_result) is None:
                # job record was created but the task is not yet started
                if first_task:
                    return CeleryTaskModel.PENDING

                # we had some tasks finished before
                return CeleryTaskModel.STARTED

            first_task = False

            # if the current task status is SUCCESS, we need to check the next
            # one
            if (status := result.status) != CeleryTaskModel.SUCCESS:
                return status

        return CeleryTaskModel.SUCCESS


class CreateDeduplicationSetSerializer(serializers.ModelSerializer):
    reference_pk = serializers.CharField(source="group.reference_pk")
    name = serializers.CharField(source="group.name", required=False, allow_null=True, allow_blank=True)
    state = serializers.CharField(source="get_state_display", read_only=True)
    settings = serializers.JSONField(required=True)

    class Meta:
        model = DeduplicationSet
        fields = ("reference_pk", "name", "notification_url", "notify", "state", "settings")
        write_only_fields = ("settings",)


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
        encoding = getattr(duplicate, f"{self._prefix}_encoding", None)
        return encoding.reference_pk if encoding else ""

    def get_filename(self, duplicate: Finding) -> str:
        encoding = getattr(duplicate, f"{self._prefix}_encoding", None)
        return encoding.filename if encoding else ""


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
    action = serializers.ChoiceField(choices=("approve", "reject"), required=True)
    reference_pks = serializers.ListField(child=serializers.CharField(), required=True)
