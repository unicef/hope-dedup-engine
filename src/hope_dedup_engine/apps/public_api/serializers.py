from rest_framework import serializers

from hope_dedup_engine.apps.public_api.models import DeduplicationSet
from hope_dedup_engine.apps.public_api.models.deduplication import Image


class DeduplicationSetSerializer(serializers.ModelSerializer):
    state = serializers.CharField(source="get_state_display", read_only=True)

    class Meta:
        model = DeduplicationSet
        exclude = ("deleted",)
        read_only_fields = "external_system", "created_at", "created_by", "deleted", "updated_at", "updated_by"


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = "__all__"
        read_only_fields = "created_by", "created_at"
