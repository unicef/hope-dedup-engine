from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from hope_dedup_engine.apps.facerecognize.models import DeduplicationTask
from hope_dedup_engine.apps.facerecognize.serializers import (
    DeduplicationRequestSerializer,
    DeduplicationResult,
    DeduplicationResultSerializer,
)
from hope_dedup_engine.apps.facerecognize.tasks import deduplicate_faces


class InitiateDeduplication(APIView):
    def post(self, request):
        serializer = DeduplicationRequestSerializer(data=request.data)
        if serializer.is_valid():
            deduplication_type = serializer.validated_data["type"]

            if deduplication_type == "face":
                task_result = deduplicate_faces.delay(serializer.validated_data["payload"])
            # elif deduplication_type == 'voice':
            #     task_result = deduplicate_voices.delay(serializer.validated_data['payload'])
            else:
                return Response({"error": "Invalid deduplication type"}, status=status.HTTP_400_BAD_REQUEST)

            task = DeduplicationTask.objects.create(task_id=task_result)
            return Response({"task_id": task.task_id}, status=status.HTTP_202_ACCEPTED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RetrieveDeduplicationResults(APIView):
    def get(self, request, task_id):
        try:
            task = DeduplicationTask.objects.get(task_id=task_id)
        except DeduplicationTask.DoesNotExist:
            return Response({"error": "Task not found"}, status=status.HTTP_404_NOT_FOUND)

        results = DeduplicationResult.objects.filter(task=task)
        serializer = DeduplicationResultSerializer(results, many=True)
        return Response(serializer.data)
