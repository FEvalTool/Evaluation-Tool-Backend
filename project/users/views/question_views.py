import logging

from django.http import JsonResponse
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework.exceptions import ValidationError

from common.constants import ErrorTypes
from ..constants import EventType
from ..models import SecurityQuestion
from ..serializers import (
    CreateSecurityQuestionSerializer,
    SecurityQuestionQuerySerializer,
    SecurityQuestionSerializer,
)

logger = logging.getLogger(__name__)


class QuestionViewSet(ViewSet):
    """
    Viewset for support Security questions related APIs
    (Create, Retrieve, Update security questions)
    """

    # def create(self, request):
    #     """
    #     Endpoint to create security questions
    #     """
    #     try:
    #         logger.info(
    #             {
    #                 "event_type": EventType.CREATE_SECURITY_QUESTIONS,
    #                 "message": "Begin create security questions",
    #             }
    #         )
    #         serializer = CreateSecurityQuestionSerializer(data=request.data, many=True)
    #         serializer.is_valid(raise_exception=True)
    #         data = serializer.validated_data
    #         security_question_instances = [
    #             SecurityQuestion(content=question["content"]) for question in data
    #         ]
    #         SecurityQuestion.objects.bulk_create(security_question_instances)
    #         logger.info(
    #             {
    #                 "event_type": EventType.CREATE_SECURITY_QUESTIONS,
    #                 "message": "Create security questions success",
    #             }
    #         )
    #         return JsonResponse(
    #             {"message": "Successfully create security questions"},
    #             status=status.HTTP_201_CREATED,
    #         )
    #     except ValidationError as e:
    #         logger.error(
    #             {
    #                 "event_type": EventType.CREATE_SECURITY_QUESTIONS,
    #                 "error_type": ErrorTypes.REQUEST_VALIDATION,
    #                 "error_content": e.detail,
    #             }
    #         )
    #         return JsonResponse(
    #             {
    #                 "message": "Invalid request",
    #                 "error_content": e.detail,
    #             },
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )
    #     except Exception as e:
    #         logger.error(
    #             {
    #                 "event_type": EventType.CREATE_SECURITY_QUESTIONS,
    #                 "error_type": ErrorTypes.EXCEPTION,
    #                 "error_content": str(e),
    #             }
    #         )
    #         return JsonResponse(
    #             {"message": "Internal server error", "error_content": str(e)},
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         )

    def list(self, request):
        """
        Endpoint to list security questions
        """
        try:
            logger.info(
                {
                    "event_type": EventType.LIST_SECURITY_QUESTIONS,
                    "message": "Begin retrieve security questions",
                }
            )
            serializer = SecurityQuestionQuerySerializer(data=request.query_params)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            queryset = SecurityQuestion.objects.all()
            if "status" in data:
                queryset = queryset.filter(status=data["status"])
            logger.info(
                {
                    "event_type": EventType.LIST_SECURITY_QUESTIONS,
                    "message": "Retrieve security questions success",
                }
            )
            serializer = SecurityQuestionSerializer(queryset, many=True)
            return JsonResponse(
                {
                    "message": "Successfully retrieve security questions",
                    "questions": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.LIST_SECURITY_QUESTIONS,
                    "error_type": ErrorTypes.REQUEST_VALIDATION,
                    "error_content": e.detail,
                }
            )
            return JsonResponse(
                {
                    "message": "Invalid request",
                    "error_content": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.LIST_SECURITY_QUESTIONS,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
