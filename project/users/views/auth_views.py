from django.http import JsonResponse

from rest_framework import status, serializers
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

import logging

from ..models import CustomUser, UserQuestionAnswer
from ..serializers import (
    UserLoginSerializer,
    GetSecurityQAVerificationTokenSerializer,
)
from common.constants import ErrorTypes
from ..constants import EventType, TokenScope
from ..exceptions import SecurityQAValidationException
from ..utils import create_jwt

logger = logging.getLogger(__name__)


class AuthViewSet(ViewSet):
    """
    Viewset for support Authentication and Authorization related APIs
    (Login, Logout, Generate Token)
    """

    @action(detail=False, methods=["post"], url_path="login")
    def login(self, request):
        """
        Endpoint to login user account
        """
        try:
            logger.info(
                {
                    "event_type": EventType.LOGIN,
                    "message": "Login user account",
                }
            )
            serializer = UserLoginSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = CustomUser.objects.get(
                username=serializer.validated_data["username"]
            )
            # Validate password
            if not user.check_password(serializer.validated_data["password"]):
                raise CustomUser.DoesNotExist
            # Create token for user
            tokens = {
                "access": create_jwt(
                    {
                        "username": user.username,
                        "name": user.name,
                    }
                )
            }
            if user.is_default_password or not user.is_security_question_set:
                tokens["password_verification"] = create_jwt(
                    {
                        "username": user.username,
                        "scope": TokenScope.PASSWORD_VERIFY_SCOPE,
                    }
                )
            logger.info(
                {
                    "event_type": EventType.LOGIN,
                    "message": "Login success",
                    "username": user.username,
                    "is_default_password": user.is_default_password,
                    "is_security_question_set": user.is_security_question_set,
                }
            )
            return JsonResponse(
                {
                    "message": "Successfully Login",
                    "tokens": tokens,
                    "is_default_password": user.is_default_password,
                    "is_security_question_set": user.is_security_question_set,
                },
            )
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.LOGIN,
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
                    "event_type": EventType.LOGIN,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": "Invalid username or password",
                }
            )
            return JsonResponse(
                {"message": "Invalid username or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.LOGIN,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="token/qa")
    def generate_question_answer_verification_token(self, request):
        """
        Endpoint to generate token when user answer security questions
        """
        try:
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
                    "message": "Begin generate security qa verification token",
                }
            )
            serializer = GetSecurityQAVerificationTokenSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            username = serializer.validated_data["username"]
            user = CustomUser.objects.get(username=username)
            if not user.is_security_question_set or user.is_default_password:
                # If user has't login to setup for the first time, return error response
                logger.error(
                    {
                        "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                        "scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
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
            # Verify security question answer
            question_ids = serializer.validated_data["questions"]
            user_qa = UserQuestionAnswer.objects.filter(
                user_id=user.id, question_id__in=question_ids
            )
            if user_qa.count() != len(serializer.validated_data["questions"]):
                raise serializers.ValidationError(
                    {"questions": ["User security questions doesn't existed"]}
                )
            correct_answers = [
                user_qa.get(question_id=id).answer for id in question_ids
            ]
            user_answers = serializer.validated_data["answers"]
            for expected, returned in zip(correct_answers, user_answers):
                if expected != returned:
                    raise SecurityQAValidationException(
                        "Security answers aren't correct"
                    )
            # Generate security qa verification token
            token = create_jwt(
                {
                    "username": username,
                    "scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
                }
            )
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
                    "message": "Get security qa verification token successfully",
                    "username": username,
                }
            )
            return JsonResponse(
                {
                    "message": "Token generated successfully",
                    "token": token,
                },
            )
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
                    "error_content": e.detail,
                }
            )
            return JsonResponse(
                {
                    "message": "Invalid request",
                    "error_type": ErrorTypes.REQUEST_VALIDATION,
                    "error_content": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": "Username not found",
                }
            )
            return JsonResponse(
                {"message": "Username not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except SecurityQAValidationException as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
                    "error_type": ErrorTypes.SECURITY_QA_VALIDATION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Security QA validation failed"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="token/password")
    def generate_password_verification_token(self, request):
        """
        Endpoint to generate token when user enter password
        """
        try:
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.PASSWORD_VERIFY_SCOPE,
                    "message": "Begin generate password verification token",
                }
            )
            serializer = UserLoginSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            username = serializer.validated_data["username"]
            user = CustomUser.objects.get(username=username)
            if not user.is_security_question_set or user.is_default_password:
                # If user has't login to setup for the first time, return error response
                logger.error(
                    {
                        "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                        "scope": TokenScope.PASSWORD_VERIFY_SCOPE,
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
            # Validate password
            if not user.check_password(serializer.validated_data["password"]):
                raise CustomUser.DoesNotExist
            # Generate password verification token
            token = create_jwt(
                {
                    "username": username,
                    "scope": TokenScope.PASSWORD_VERIFY_SCOPE,
                }
            )
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.PASSWORD_VERIFY_SCOPE,
                    "message": "Get password verification token successfully",
                    "username": username,
                }
            )
            return JsonResponse(
                {
                    "message": "Token generated successfully",
                    "token": token,
                },
            )
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.PASSWORD_VERIFY_SCOPE,
                    "error_content": e.detail,
                }
            )
            return JsonResponse(
                {
                    "message": "Invalid request",
                    "error_type": ErrorTypes.REQUEST_VALIDATION,
                    "error_content": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.PASSWORD_VERIFY_SCOPE,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": "Invalid username or password",
                }
            )
            return JsonResponse(
                {"message": "Invalid username or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.PASSWORD_VERIFY_SCOPE,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
