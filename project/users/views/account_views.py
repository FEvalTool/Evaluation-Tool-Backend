import logging

from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.conf import settings
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import UntypedToken

from common.constants import ErrorTypes
from ..models import CustomUser, UserQuestionAnswer
from ..serializers import (
    InitAccountSerializer,
    GetAccountInfoSerializer,
    SetPasswordSerializer,
    SetSecurityQASerializer,
    GetSecurityQuestionParamsSerializer,
)
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

    @action(detail=False, methods=["get"], url_path="setup_status")
    def get_user_setup_status(self, request):
        """
        Endpoint to get user setup status
        (password setup status/security qa setup status)
        """
        try:
            # Try to find token in cookie
            # (access token priority, if no access token, find scope token)
            token = get_token_from_cookie(
                request, settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"], True
            )
            if not token:
                token = get_token_from_cookie(
                    request, settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"], False
                )
            payload = UntypedToken(token)
            user = CustomUser.objects.get(id=payload.get("user_id"))
            user_data = {"id": user.id, "username": user.username}
            # Add user setup status if user is newly created one
            if user.is_default_password or not user.is_security_question_set:
                user_data["first_time_setup"] = True
                user_data["is_password_setup"] = not user.is_default_password
                user_data["is_security_qa_setup"] = user.is_security_question_set
            return JsonResponse(
                {"message": "Retrieve user setup status success", "user": user_data},
                status=status.HTTP_200_OK,
            )
        except TokenNotFoundException as e:
            logger.error(
                {
                    "event_type": EventType.GET_USER_INFO,
                    "error_type": ErrorTypes.TOKEN_NOT_FOUND,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Token not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.GET_USER_INFO,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": f"Account with id {payload.get('user_id')} is not existed",
                }
            )
            return JsonResponse(
                {"message": "Account invalid or deleted"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.GET_USER_INFO,
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
                status=status.HTTP_401_UNAUTHORIZED,
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
                    "error_content": f"Account with id {payload.get('user_id')} is not existed",
                }
            )
            return JsonResponse(
                {"message": "Account invalid or deleted"},
                status=status.HTTP_401_UNAUTHORIZED,
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

    @action(detail=False, methods=["get", "post"], url_path="security_questions")
    def user_security_questions(self, request):
        if request.method == "GET":
            return self.get_user_security_questions(request)
        if request.method == "POST":
            return self.set_security_question_answer(request)

    def set_security_question_answer(self, request):
        """
        Endpoint to set new security question answer (for the first time/reset security question)
        """
        try:
            logger.info(
                {
                    "event_type": EventType.SET_SECURITY_QA,
                    "message": "Begin set security question answer process",
                }
            )
            # Extract token from request and verify scope
            token = get_token_from_cookie(
                request, settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"], False
            )
            check_token_validity(token, settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"])
            payload = ScopeToken(token)
            payload.verify_scope([TokenScope.PASSWORD_VERIFY_SCOPE])
            # Validate security qa
            serializer = SetSecurityQASerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            # Delete old security question answer of current user
            # and replace with the new one
            logger.info(
                {
                    "event_type": EventType.SET_SECURITY_QA,
                    "message": "Reset security question if exist",
                }
            )
            user = CustomUser.objects.get(id=payload.get("user_id"))
            old_security_questions = UserQuestionAnswer.objects.filter(user=user.id)
            old_security_questions.delete()
            new_security_questions = []
            for question, answer in zip(
                serializer.validated_data["questions"],
                serializer.validated_data["answers"],
            ):
                new_security_questions.append(
                    UserQuestionAnswer(question=question, answer=answer, user=user)
                )
            UserQuestionAnswer.objects.bulk_create(new_security_questions)

            if not user.is_security_question_set:
                # If user set security question for the first time, set this flag to true
                user.is_security_question_set = True
                user.save()
            logger.info(
                {
                    "event_type": EventType.SET_SECURITY_QA,
                    "message": "Reset security question successfull",
                }
            )
            return JsonResponse(
                {"message": "Successfully set new security question and answer"}
            )
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.SET_SECURITY_QA,
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
                    "event_type": EventType.SET_SECURITY_QA,
                    "error_type": ErrorTypes.TOKEN_NOT_FOUND,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except TokenError as e:
            logger.error(
                {
                    "event_type": EventType.SET_SECURITY_QA,
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
                    "event_type": EventType.SET_SECURITY_QA,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": f"Account with id {payload['user_id']} is not existed",
                }
            )
            return JsonResponse(
                {"message": "Account invalid or deleted"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.SET_SECURITY_QA,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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
                        "error_content": f"Account with username {username} hasn't setup account",
                        "is_security_question_set": user.is_security_question_set,
                        "is_default_password": user.is_default_password,
                    }
                )
                return JsonResponse(
                    {
                        "message": f"Account with username {username} hasn't setup account"
                    },
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
                    "error_content": f"Account with username {username} is not existed",
                }
            )
            return JsonResponse(
                {"message": f"Account with username {username} is not existed"},
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
