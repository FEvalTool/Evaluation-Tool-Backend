import logging

from django.http import JsonResponse
from django.conf import settings
from rest_framework import status, serializers, response
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.exceptions import TokenError

from ..models import CustomUser, UserQuestionAnswer
from ..serializers import (
    UserLoginSerializer,
    GetSecurityQAVerificationTokenSerializer,
    TokenTypeSerializer,
)
from common.constants import ErrorTypes
from ..constants import EventType, TokenScope, BYPASS_TOKEN_NOTFOUND
from ..exceptions import SecurityQAValidationException, TokenNotFoundException
from ..custom_token import ScopeToken
from ..utils import (
    get_token_from_cookie,
    store_blacklist_token,
    check_token_validity,
)

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
                    path=settings.COOKIE_SETTINGS["AUTH_COOKIE_PATH"],
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
                    path=settings.COOKIE_SETTINGS["AUTH_COOKIE_PATH"],
                )
                res.set_cookie(
                    key=settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"],
                    value=str(refresh),
                    max_age=api_settings.REFRESH_TOKEN_LIFETIME.total_seconds(),
                    secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
                    httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
                    samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
                    path=settings.COOKIE_SETTINGS["AUTH_COOKIE_PATH"],
                )
            response_data["user"] = user_data
            res.data = response_data
            logger.info(
                {
                    "event_type": EventType.LOGIN,
                    "message": "Login success",
                    "username": user.username,
                    "is_default_password": user.is_default_password,
                    "is_security_question_set": user.is_security_question_set,
                }
            )
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
            token_instance = ScopeToken.for_user(
                user, TokenScope.SECURITY_QUESTION_VERIFY_SCOPE
            )
            token = str(token_instance)
            exp = token_instance.payload.get("exp")
            res = response.Response()
            res.set_cookie(
                key=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                value=token,
                max_age=settings.SCOPE_TOKEN_LIFETIME_MINUTES.total_seconds(),
                secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
                httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
                samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
                path=settings.COOKIE_SETTINGS["AUTH_COOKIE_PATH"],
            )
            # Convert exp to milliseconds
            res.data = {"message": "Token generated successfully", "exp": exp * 1000}
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
                    "message": "Get security qa verification token successfully",
                    "username": username,
                }
            )
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
            token_instance = ScopeToken.for_user(user, TokenScope.PASSWORD_VERIFY_SCOPE)
            token = str(token_instance)
            exp = token_instance.payload.get("exp")
            res = response.Response()
            res.set_cookie(
                key=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                value=token,
                max_age=settings.SCOPE_TOKEN_LIFETIME_MINUTES.total_seconds(),
                secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
                httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
                samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
                path=settings.COOKIE_SETTINGS["AUTH_COOKIE_PATH"],
            )
            # Convert exp to milliseconds
            res.data = {"message": "Token generated successfully", "exp": exp * 1000}
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": TokenScope.PASSWORD_VERIFY_SCOPE,
                    "message": "Get password verification token successfully",
                    "username": username,
                }
            )
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
        Endpoint to verify token validity in cookie
        """
        try:
            logger.info(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "message": "Begin verify token",
                }
            )
            serializer = TokenTypeSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            token = get_token_from_cookie(
                request, serializer.validated_data["token_type"], False
            )
            check_token_validity(token, serializer.validated_data["token_type"])
            logger.info(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "message": "Token is valid",
                }
            )
            return JsonResponse({"message": "Token is valid"})
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
                request, settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"], False
            )
            # Check if refresh token is valid and not in blacklisted
            check_token_validity(token, settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"])
            # Get new access and refresh token
            serializer = TokenRefreshSerializer(data={"refresh": token})
            # Store old refresh token in blacklist
            store_blacklist_token(
                token, settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]
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
                path=settings.COOKIE_SETTINGS["AUTH_COOKIE_PATH"],
            )
            res.set_cookie(
                key=settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"],
                value=serializer.validated_data.get("refresh", token),
                max_age=api_settings.REFRESH_TOKEN_LIFETIME.total_seconds(),
                secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
                httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
                samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
                path=settings.COOKIE_SETTINGS["AUTH_COOKIE_PATH"],
            )
            res.data = response_data
            logger.info(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "message": "Token is refreshed",
                }
            )
            return res
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

    @action(detail=False, methods=["post"], url_path="token/scope/delete")
    def delete_scope_token(self, request):
        """
        Endpoint to delete scope tokens from cookies
        """
        try:
            logger.info(
                {
                    "event_type": EventType.DELETE_SCOPE_TOKEN,
                    "message": "Begin delete scope token from cookies",
                }
            )
            bypass_token_notfound_err = request.data.get(BYPASS_TOKEN_NOTFOUND, True)
            res = response.Response()
            # Validate token existence
            token = get_token_from_cookie(
                request,
                settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                bypass_token_notfound_err,
            )
            # Delete scope token from cookies
            res.delete_cookie(key=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"])
            # Store deleted scope token in blacklist
            if token:
                store_blacklist_token(
                    token, settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]
                )
            res.data = {"message": "Scope tokens deleted successfully"}
            logger.info(
                {
                    "event_type": EventType.DELETE_SCOPE_TOKEN,
                    "message": "Scope token deleted successfully from cookies",
                }
            )
            return res
        except TokenNotFoundException as e:
            logger.error(
                {
                    "event_type": EventType.DELETE_SCOPE_TOKEN,
                    "error_type": ErrorTypes.TOKEN_NOT_FOUND,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.DELETE_SCOPE_TOKEN,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="logout")
    def delete_refresh_access_token(self, request):
        """
        Endpoint to delete access and refresh tokens from cookies
        (Logout normal user)
        """
        try:
            logger.info(
                {
                    "event_type": EventType.LOGOUT,
                    "message": "Begin logout",
                }
            )
            bypass_token_notfound_err = request.data.get(BYPASS_TOKEN_NOTFOUND, True)
            # Validate token existence
            get_token_from_cookie(
                request,
                settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"],
                bypass_token_notfound_err,
            )
            refresh_token = get_token_from_cookie(
                request,
                settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"],
                bypass_token_notfound_err,
            )
            res = response.Response()
            # Delete tokens from cookies
            res.delete_cookie(key=settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"])
            res.delete_cookie(key=settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"])
            # Store deleted refresh token in blacklist
            if refresh_token:
                store_blacklist_token(
                    refresh_token, settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]
                )
            res.data = {"message": "Logout successfully"}
            logger.info(
                {
                    "event_type": EventType.LOGOUT,
                    "message": "Logout successful",
                }
            )
            return res
        except TokenNotFoundException as e:
            logger.error(
                {
                    "event_type": EventType.LOGOUT,
                    "error_type": ErrorTypes.TOKEN_NOT_FOUND,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.LOGOUT,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Internal server error", "error_content": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
