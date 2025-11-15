import logging

from django.http import JsonResponse
from django.conf import settings
from rest_framework import status, serializers, response
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import (
    TokenVerifySerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.exceptions import TokenError

from ..models import CustomUser, UserQuestionAnswer
from ..serializers import (
    UserLoginSerializer,
    GetSecurityQAVerificationTokenSerializer,
)
from common.constants import ErrorTypes
from ..constants import EventType, TokenScope
from ..exceptions import SecurityQAValidationException, TokenNotFoundException
from ..custom_token import ScopeToken
from ..utils import get_token_from_cookie

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
            res = response.Response()
            response_data = {"message": "Successfully Login"}
            user_data = {"id": user.id, "username": user.username}
            # Create and store token in cookie
            if user.is_default_password or not user.is_security_question_set:
                # When user login for the first time, create scope jwt token
                scope_token = ScopeToken.for_user(
                    user, TokenScope.PASSWORD_VERIFY_SCOPE
                )
                res.set_cookie(
                    key=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                    value=str(scope_token),
                    max_age=api_settings.ACCESS_TOKEN_LIFETIME.total_seconds(),
                    secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
                    httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
                    samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
                )
                user_data["first_time_setup"] = True
                user_data["is_password_setup"] = not user.is_default_password
                user_data["is_security_qa_setup"] = user.is_security_question_set
            else:
                refresh = RefreshToken.for_user(user)
                res.set_cookie(
                    key=settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"],
                    value=str(refresh.access_token),
                    max_age=api_settings.ACCESS_TOKEN_LIFETIME.total_seconds(),
                    secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
                    httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
                    samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
                )
                res.set_cookie(
                    key=settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"],
                    value=str(refresh),
                    max_age=api_settings.REFRESH_TOKEN_LIFETIME.total_seconds(),
                    secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
                    httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
                    samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
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
            response_data["user"] = user_data
            res.data = response_data
            return res
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
            token = str(
                ScopeToken.for_user(user, TokenScope.SECURITY_QUESTION_VERIFY_SCOPE)
            )
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
                    "message": "Get security qa verification token successfully",
                    "username": username,
                }
            )
            res = response.Response()
            res.set_cookie(
                key=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                value=token,
                max_age=settings.SCOPE_TOKEN_LIFETIME_MINUTES.total_seconds(),
                secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
                httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
                samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
            )
            res.data = {"message": "Token generated successfully"}
            return res
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
            token = str(ScopeToken.for_user(user, TokenScope.PASSWORD_VERIFY_SCOPE))
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.PASSWORD_VERIFY_SCOPE,
                    "message": "Get password verification token successfully",
                    "username": username,
                }
            )
            res = response.Response()
            res.set_cookie(
                key=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                value=token,
                max_age=settings.SCOPE_TOKEN_LIFETIME_MINUTES.total_seconds(),
                secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
                httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
                samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
            )
            res.data = {"message": "Token generated successfully"}
            return res
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

    @action(detail=False, methods=["post"], url_path="token/verify")
    def verify_token(self, request):
        """
        Endpoint to verify access token validity in cookie
        """
        try:
            logger.info(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "message": "Begin verify token",
                }
            )
            if request.body.get("token_type") == "scope":
                cookie_name = settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]
            elif request.body.get("token_type") == "access":
                cookie_name = settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]
            else:
                raise ValidationError(
                    {"token_type": ["token_type must be 'scope' or 'access'"]}
                )
            token = get_token_from_cookie(request, cookie_name)
            serializer = TokenVerifySerializer(data={"token": token})
            serializer.is_valid(raise_exception=True)
            logger.info(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "message": "Token is valid",
                }
            )
            return JsonResponse(
                {
                    "message": "Token is valid",
                },
            )
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.VERIFY_TOKEN,
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
                    "event_type": EventType.VERIFY_TOKEN,
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
                    "event_type": EventType.VERIFY_TOKEN,
                    "error_type": ErrorTypes.TOKEN_VALIDATION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Invalid token", "error_content": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="token/refresh")
    def refresh_token(self, request):
        """
        Endpoint to refresh access token using refresh token
        """
        try:
            logger.info(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "message": "Begin refresh access token",
                }
            )
            token = get_token_from_cookie(
                request, settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]
            )
            serializer = TokenRefreshSerializer(data={"refresh": token})
            serializer.is_valid(raise_exception=True)
            logger.info(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "message": "Token is refreshed",
                }
            )
            res = response.Response()
            response_data = {"message": "Refresh token successful"}
            res.set_cookie(
                key=settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"],
                value=serializer.validated_data["access"],
                max_age=api_settings.ACCESS_TOKEN_LIFETIME.total_seconds(),
                secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
                httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
                samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
            )
            res.data = response_data
            return res
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.REFRESH_TOKEN,
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
                    "event_type": EventType.REFRESH_TOKEN,
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
                    "event_type": EventType.REFRESH_TOKEN,
                    "error_type": ErrorTypes.TOKEN_VALIDATION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Invalid token", "error_content": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
