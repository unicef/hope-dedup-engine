from rest_framework import serializers

from hope_dedup_engine.apps.facerecognize.models import DeduplicationResult


class DeduplicationRequestSerializer(serializers.Serializer):
    type = serializers.CharField(max_length=50)
    data = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField())  # Assuming UUID and image_path are strings
    )


class DeduplicationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeduplicationResult
        fields = ["uuid1", "uuid2", "similarity_score"]
