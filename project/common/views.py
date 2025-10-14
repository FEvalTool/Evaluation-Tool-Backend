from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.decorators import action

class HealthViewSet(ViewSet):
    """
    ViewSet for health check endpoint
    """
    @action(detail=False, methods=["get"], url_path="check")
    def check(self, request):
        return Response({
            "message": "Hello, this is Evaluation Tool Project. This project is a refactor version of the C99 Training Python project for intern and OJT in FPT Software."
        })
