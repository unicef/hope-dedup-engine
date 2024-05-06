from rest_framework import serializers

from hope_dedup_engine.apps.public_api.models import DeduplicationSet


class DeduplicationSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeduplicationSet
        fields = "__all__"
        read_only_fields = "external_system", "created_at", "created_by"
