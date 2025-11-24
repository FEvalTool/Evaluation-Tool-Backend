import logging

from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.conf import settings
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import TokenError

from ..models import CustomUser, UserQuestionAnswer
from ..serializers import (
    InitAccountSerializer,
    SetPasswordSerializer,
    GetSecurityQuestionParamsSerializer,
)
from common.constants import ErrorTypes
from ..constants import EventType, TokenScope
from ..utils import generate_username, get_token_from_cookie, check_token_validity
from ..custom_token import ScopeToken
from ..exceptions import TokenNotFoundException

logger = logging.getLogger(__name__)


class AccountViewSet(ViewSet):
    """
    Viewset for support Account related APIs
    (Create, Update, Delete)
    """

    def create(self, request):
        """
        Endpoint to initialize user account
        """
        try:
            logger.info(
                {
                    "event_type": EventType.CREATE_USER_ACCOUNT,
                    "message": "Begin initialize user account",
                }
            )
            serializer = InitAccountSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            # Set initial password and username
            response_data = {
                "username": generate_username(data["name"]),
                "password": get_random_string(length=12),
            }
            data["username"] = response_data["username"]
            user = CustomUser(**data)
            user.set_password(response_data["password"])
            user.save()
            logger.info(
                {
                    "event_type": EventType.CREATE_USER_ACCOUNT,
                    "message": "Initialize user account success",
                }
            )
            return JsonResponse(
                {"message": "Successfully intialize account", "data": response_data},
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.CREATE_USER_ACCOUNT,
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
                    "event_type": EventType.CREATE_USER_ACCOUNT,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="password")
    def set_password(self, request):
        """
        Endpoint to update password
        """
        try:
            logger.info(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "message": "Begin set new password process",
                }
            )
            # Extract token from request and verify scope
            token = get_token_from_cookie(
                request, settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"], False
            )
            check_token_validity(token, settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"])
            payload = ScopeToken(token)
            payload.verify_scope(
                [
                    TokenScope.PASSWORD_VERIFY_SCOPE,
                    TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
                ]
            )
            # Validate new password
            serializer = SetPasswordSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            # Update new password for user
            user = CustomUser.objects.get(id=payload.get("user_id"))
            user.set_password(serializer.validated_data["password"])
            if user.is_default_password:
                # If user change the password for the first time, set this flag to false
                user.is_default_password = False
            user.save()
            logger.info(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "user_id": payload.get("user_id"),
                    "message": "Set new password success",
                }
            )
            return JsonResponse({"message": "Successfully set new password"})
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.SET_PASSWORD,
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
        except TokenNotFoundException as e:
            logger.error(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "error_type": ErrorTypes.TOKEN_NOT_FOUND,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TokenError as e:
            logger.error(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "error_type": ErrorTypes.TOKEN_VALIDATION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Invalid token", "error_content": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": f"User with id {payload.get('user_id')} is not existed",
                }
            )
            return JsonResponse(
                {"message": f"User is not existed"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # @action(detail=False, methods=["post"], url_path="security_questions")
    # def set_security_question_answer(self, request):
    #     """
    #     Endpoint to set new security question answer (for the first time/reset security question)
    #     """
    #     try:
    #         logger.info(
    #             {
    #                 "event_type": EventType.SET_SECURITY_QA,
    #                 "message": "Begin set security question answer process",
    #             }
    #         )
    #         serializer = SetSecurityQASerializer(data=request.data)
    #         serializer.is_valid(raise_exception=True)
    #         payload = decode_and_verify_jwt(
    #             serializer.validated_data["token"], verify_is_able_to_set_security_qa
    #         )
    #         # Delete old security question answer of current user
    #         # and replace with the new one
    #         logger.info(
    #             {
    #                 "event_type": EventType.SET_SECURITY_QA,
    #                 "message": "Reset security question if exist",
    #             }
    #         )
    #         user = CustomUser.objects.get(username=payload["username"])
    #         old_security_questions = UserQuestionAnswer.objects.filter(user=user.id)
    #         old_security_questions.delete()
    #         new_security_questions = []
    #         for question, answer in zip(
    #             serializer.validated_data["questions"],
    #             serializer.validated_data["answers"],
    #         ):
    #             new_security_questions.append(
    #                 UserQuestionAnswer(question=question, answer=answer, user=user)
    #             )
    #         UserQuestionAnswer.objects.bulk_create(new_security_questions)

    #         if not user.is_security_question_set:
    #             # If user set security question for the first time, set this flag to true
    #             user.is_security_question_set = True
    #             user.save()
    #         logger.info(
    #             {
    #                 "event_type": EventType.SET_SECURITY_QA,
    #                 "message": "Reset security question successfull",
    #             }
    #         )
    #         return JsonResponse(
    #             {"message": "Successfully set new security question and answer"}
    #         )
    #     except ValidationError as e:
    #         logger.error(
    #             {
    #                 "event_type": EventType.SET_SECURITY_QA,
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
    #     except TokenValidationException as e:
    #         logger.error(
    #             {
    #                 "event_type": EventType.SET_SECURITY_QA,
    #                 "error_type": ErrorTypes.TOKEN_VALIDATION,
    #                 "error_content": str(e),
    #             }
    #         )
    #         return JsonResponse(
    #             {"message": "Token validation failed", "error_content": str(e)},
    #             status=status.HTTP_401_UNAUTHORIZED,
    #         )
    #     except CustomUser.DoesNotExist:
    #         logger.error(
    #             {
    #                 "event_type": EventType.SET_SECURITY_QA,
    #                 "error_type": ErrorTypes.UNEXISTED,
    #                 "error_content": f"User with username {payload['username']} is not existed",
    #             }
    #         )
    #         return JsonResponse(
    #             {"message": f"User with username {payload['username']} is not existed"},
    #             status=status.HTTP_404_NOT_FOUND,
    #         )
    #     except Exception as e:
    #         logger.error(
    #             {
    #                 "event_type": EventType.SET_SECURITY_QA,
    #                 "error_type": ErrorTypes.EXCEPTION,
    #                 "error_content": str(e),
    #             }
    #         )
    #         return JsonResponse(
    #             {"message": "Internal server error", "error_content": str(e)},
    #             status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         )

    @action(detail=False, methods=["get"], url_path="security_questions")
    def get_user_security_questions(self, request):
        """
        Endpoint to get user security question (for forgot password)
        """
        try:
            logger.info(
                {
                    "event_type": EventType.GET_USER_SECURITY_QUESTIONS,
                    "message": "Begin retrieve user security question process",
                }
            )
            query_serializer = GetSecurityQuestionParamsSerializer(
                data=request.query_params
            )
            query_serializer.is_valid(raise_exception=True)
            username = query_serializer.validated_data["username"]
            user = CustomUser.objects.get(username=username)
            if not user.is_security_question_set or user.is_default_password:
                # If user has't login to setup for the first time, return error response
                logger.error(
                    {
                        "event_type": EventType.GET_USER_SECURITY_QUESTIONS,
                        "error_type": ErrorTypes.UNAUTHORIZED,
                        "error_content": f"User {username} hasn't setup account",
                        "is_security_question_set": user.is_security_question_set,
                        "is_default_password": user.is_default_password,
                    }
                )
                return JsonResponse(
                    {"message": f"User {username} hasn't setup account"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            security_questions = UserQuestionAnswer.objects.filter(
                user=user.id
            ).values_list("question_id", "question__content")
            questions_dict = dict(security_questions)  # format: {id: question}
            # Convert from {id: question} to [{"id": id, "question": question}]
            questions_list = [
                {"id": key, "content": value} for key, value in questions_dict.items()
            ]
            logger.info(
                {
                    "event_type": EventType.GET_USER_SECURITY_QUESTIONS,
                    "message": "Retrieve user security question successfull",
                }
            )
            return JsonResponse(
                {
                    "message": "Retrieve user security questions successful",
                    "questions": questions_list,
                }
            )
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.GET_USER_SECURITY_QUESTIONS,
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
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.GET_USER_SECURITY_QUESTIONS,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": f"User with username {username} is not existed",
                }
            )
            return JsonResponse(
                {"message": f"User with username {username} is not existed"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.GET_USER_SECURITY_QUESTIONS,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
