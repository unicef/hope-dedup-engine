from rest_framework import serializers

from hope_dedup_engine.apps.public_api.models import DeduplicationSet


class DeduplicationSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeduplicationSet
        fields = "__all__"
