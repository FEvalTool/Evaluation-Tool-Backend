import logging

from django.http import JsonResponse
from django.conf import settings
from rest_framework import serializers, response
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import (
    ValidationError,
    APIException,
    AuthenticationFailed,
    PermissionDenied,
    NotAuthenticated,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.exceptions import TokenError

from ..models import CustomUser, UserQuestionAnswer
from ..serializers.auth_serializers import (
    PasswordVerificationRequest,
    SecurityQAVerificationRequest,
    VerifyTokenRequest,
)
from core.constants import ErrorTypes, EventType
from core.auth.tokens import ScopeToken, ScopeTokenPurpose
from core.auth.utils import (
    get_token_from_cookies,
    store_blacklist_token,
    check_token_validity,
    set_auth_cookies,
    delete_auth_cookie,
)
from core.exceptions import Conflict

logger = logging.getLogger(__name__)


class AuthViewSet(ViewSet):
    """
    Viewset for support Authentication and Authorization related APIs
    (Login, Logout, Generate and Delete Token)
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
            serializer = PasswordVerificationRequest(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = CustomUser.objects.get(
                username=serializer.validated_data["username"]
            )
            # Validate password
            if not user.check_password(serializer.validated_data["password"]):
                raise CustomUser.DoesNotExist
            # Prepare cookie metadata and data for response
            response_data = {"message": "Successfully Login"}
            data = {"user": {"id": user.id, "username": user.username}}
            cookie_item_list = []
            if user.is_default_password or not user.is_security_question_set:
                # When user login for the first time, create scope jwt token
                scope_token = ScopeToken.for_user(
                    user, ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE
                )
                exp = scope_token.payload.get("exp")
                cookie_item_list.append(
                    {
                        "key": settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                        "value": str(scope_token),
                        "max_age": settings.SCOPE_TOKEN_LIFETIME.total_seconds(),
                    }
                )
                user_data = data["user"]
                user_data["first_time_setup"] = True
                user_data["is_password_setup"] = not user.is_default_password
                user_data["is_security_qa_setup"] = user.is_security_question_set
                data["user"] = user_data
                data["scope_token_exp"] = exp * 1000
            else:
                refresh = RefreshToken.for_user(user)
                cookie_item_list.extend(
                    [
                        {
                            "key": settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"],
                            "value": str(refresh.access_token),
                            "max_age": api_settings.ACCESS_TOKEN_LIFETIME.total_seconds(),
                        },
                        {
                            "key": settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"],
                            "value": str(refresh),
                            "max_age": api_settings.REFRESH_TOKEN_LIFETIME.total_seconds(),
                        },
                    ]
                )
            response_data["data"] = data
            # Store cookie and data in response
            res = response.Response()
            res = set_auth_cookies(res, cookie_item_list)
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
            raise e
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.LOGIN,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": "Invalid username or password",
                }
            )
            raise AuthenticationFailed("Invalid username or password")
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.LOGIN,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(detail=False, methods=["post"], url_path="token/qa")
    def generate_question_answer_verification_token(self, request):
        """
        Endpoint to generate token when user answer security questions
        """
        try:
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": ScopeTokenPurpose.SECURITY_QUESTION_VERIFY_SCOPE,
                    "message": "Begin generate security qa verification token",
                }
            )
            serializer = SecurityQAVerificationRequest(data=request.data)
            serializer.is_valid(raise_exception=True)
            username = serializer.validated_data["username"]
            user = CustomUser.objects.get(username=username)
            if not user.is_security_question_set or user.is_default_password:
                # If user has't login to setup for the first time, return error response
                logger.error(
                    {
                        "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                        "scope": ScopeTokenPurpose.SECURITY_QUESTION_VERIFY_SCOPE,
                        "error_type": ErrorTypes.UNAUTHORIZED,
                        "error_content": f"User with username {username} hasn't setup account",
                        "is_security_question_set": user.is_security_question_set,
                        "is_default_password": user.is_default_password,
                    }
                )
                raise PermissionDenied(
                    f"User with username {username} hasn't setup account, cannot perform this action"
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
                    raise AuthenticationFailed("Invalid security credentials provided")
            # Generate security qa verification token
            token_instance = ScopeToken.for_user(
                user, ScopeTokenPurpose.SECURITY_QUESTION_VERIFY_SCOPE
            )
            token = str(token_instance)
            exp = token_instance.payload.get("exp")
            res = response.Response()
            res = set_auth_cookies(
                res,
                [
                    {
                        "key": settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                        "value": token,
                        "max_age": settings.SCOPE_TOKEN_LIFETIME.total_seconds(),
                    }
                ],
            )
            # Convert exp to milliseconds
            res.data = {
                "message": "Token generated successfully",
                "data": {"scope_token_exp": exp * 1000},
            }
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": ScopeTokenPurpose.SECURITY_QUESTION_VERIFY_SCOPE,
                    "message": "Get security qa verification token successfully",
                    "username": username,
                }
            )
            return res
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": ScopeTokenPurpose.SECURITY_QUESTION_VERIFY_SCOPE,
                    "error_content": e.detail,
                }
            )
            raise e
        except (CustomUser.DoesNotExist, AuthenticationFailed) as e:
            if isinstance(e, CustomUser.DoesNotExist):
                error_type = ErrorTypes.UNEXISTED
                error_message = "User does not exist"
            else:
                error_type = ErrorTypes.SECURITY_QA_VALIDATION
                error_message = str(e)
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": ScopeTokenPurpose.SECURITY_QUESTION_VERIFY_SCOPE,
                    "error_type": error_type,
                    "error_content": error_message,
                }
            )
            raise AuthenticationFailed(error_message)
        except PermissionDenied as e:
            raise e
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": ScopeTokenPurpose.SECURITY_QUESTION_VERIFY_SCOPE,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(detail=False, methods=["post"], url_path="token/password")
    def generate_password_verification_token(self, request):
        """
        Endpoint to generate token when user enter password
        """
        try:
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                    "message": "Begin generate password verification token",
                }
            )
            serializer = PasswordVerificationRequest(data=request.data)
            serializer.is_valid(raise_exception=True)
            username = serializer.validated_data["username"]
            user = CustomUser.objects.get(username=username)
            if not user.is_security_question_set or user.is_default_password:
                # If user has't login to setup for the first time, return error response
                logger.error(
                    {
                        "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                        "scope": ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                        "error_type": ErrorTypes.UNAUTHORIZED,
                        "error_content": f"User with username {username} hasn't setup account",
                        "is_security_question_set": user.is_security_question_set,
                        "is_default_password": user.is_default_password,
                    }
                )
                raise PermissionDenied(
                    f"User with username {username} hasn't setup account, cannot perform this action"
                )
            # Validate password
            if not user.check_password(serializer.validated_data["password"]):
                raise CustomUser.DoesNotExist
            # Generate password verification token
            token_instance = ScopeToken.for_user(
                user, ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE
            )
            token = str(token_instance)
            exp = token_instance.payload.get("exp")
            res = response.Response()
            res = set_auth_cookies(
                res,
                [
                    {
                        "key": settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                        "value": token,
                        "max_age": settings.SCOPE_TOKEN_LIFETIME.total_seconds(),
                    }
                ],
            )
            # Convert exp to milliseconds
            res.data = {
                "message": "Token generated successfully",
                "data": {"scope_token_exp": exp * 1000},
            }
            logger.info(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                    "message": "Get password verification token successfully",
                    "username": username,
                }
            )
            return res
        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                    "error_content": e.detail,
                }
            )
            raise e
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": "Invalid username or password",
                }
            )
            raise AuthenticationFailed("Invalid security credentials provided")
        except PermissionDenied as e:
            raise e
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_VERIFICATION_TOKEN,
                    "scope": ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(detail=False, methods=["post"], url_path="token/verify")
    def verify_token(self, request):
        """
        Endpoint to verify token validity in cookie
        """
        try:
            logger.info(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "message": "Begin verify token - validate request process",
                }
            )
            serializer = VerifyTokenRequest(data=request.data)
            serializer.is_valid(raise_exception=True)
            logger.info(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "message": "Verify token - retrieve token process",
                }
            )
            token, token_type = get_token_from_cookies(
                request, [serializer.validated_data["token_type"]]
            )
            if token is None:
                raise NotAuthenticated("Token not found")
            logger.info(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "message": f"Verify token - validate {token_type} token process",
                }
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
            raise e
        except NotAuthenticated as e:
            logger.error(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "error_type": ErrorTypes.TOKEN_NOT_FOUND,
                    "error_content": str(e),
                }
            )
            raise e
        except TokenError as e:
            logger.error(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "error_type": ErrorTypes.TOKEN_VALIDATION,
                    "error_content": str(e),
                }
            )
            raise AuthenticationFailed(str(e))
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.VERIFY_TOKEN,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(detail=False, methods=["post"], url_path="token/refresh")
    def refresh_token(self, request):
        """
        Endpoint to refresh access token using refresh token
        """
        try:
            logger.info(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "message": "Begin refresh access token - retrieve token process",
                }
            )
            token, _ = get_token_from_cookies(
                request, [settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]]
            )
            if token is None:
                raise NotAuthenticated("Token not found")
            # Check if refresh token is valid and not in blacklisted
            logger.info(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "message": "Refresh access token - validate token process",
                }
            )
            check_token_validity(token, settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"])
            # Get new access and refresh token
            logger.info(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "message": "Refresh access token - refresh token process",
                }
            )
            serializer = TokenRefreshSerializer(data={"refresh": token})
            serializer.is_valid()
            # Store old refresh token in blacklist
            store_blacklist_token(
                token, settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]
            )
            # Prepare cookie metadata and data for response
            response_data = {"message": "Refresh token successful"}
            cookie_item_list = [
                {
                    "key": settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"],
                    "value": serializer.validated_data["access"],
                    "max_age": api_settings.ACCESS_TOKEN_LIFETIME.total_seconds(),
                },
                {
                    "key": settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"],
                    "value": serializer.validated_data["refresh"],
                    "max_age": api_settings.REFRESH_TOKEN_LIFETIME.total_seconds(),
                },
            ]
            # Store cookie and data in response
            res = response.Response()
            res = set_auth_cookies(res, cookie_item_list)
            res.data = response_data
            logger.info(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "message": "Token is refreshed",
                }
            )
            return res
        except NotAuthenticated as e:
            logger.error(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "error_type": ErrorTypes.TOKEN_NOT_FOUND,
                    "error_content": str(e),
                }
            )
            raise e
        except TokenError as e:
            logger.error(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "error_type": ErrorTypes.TOKEN_VALIDATION,
                    "error_content": str(e),
                }
            )
            raise AuthenticationFailed(str(e))
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.REFRESH_TOKEN,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(detail=False, methods=["post"], url_path="token/scope/delete")
    def delete_scope_token(self, request):
        """
        Endpoint to delete scope tokens from cookies
        """
        try:
            logger.info(
                {
                    "event_type": EventType.DELETE_SCOPE_TOKEN,
                    "message": "Begin delete scope token from cookies - retrieve token process",
                }
            )
            res = response.Response()
            # Validate token existence
            token, _ = get_token_from_cookies(
                request,
                [settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]],
            )
            if token is not None:
                logger.info(
                    {
                        "event_type": EventType.DELETE_SCOPE_TOKEN,
                        "message": "Delete scope token from cookies - delete token process",
                    }
                )
                # Delete scope token from cookies
                delete_auth_cookie(res, settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"])
                # Store deleted scope token in blacklist
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
        except NotAuthenticated as e:
            logger.error(
                {
                    "event_type": EventType.DELETE_SCOPE_TOKEN,
                    "error_type": ErrorTypes.TOKEN_NOT_FOUND,
                    "error_content": str(e),
                }
            )
            raise Conflict(str(e))
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.DELETE_SCOPE_TOKEN,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

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
                    "message": "Begin logout - retrieve token process",
                }
            )
            # Validate token existence
            access_token, _ = get_token_from_cookies(
                request,
                [settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]],
            )
            refresh_token, _ = get_token_from_cookies(
                request,
                [settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]],
            )
            res = response.Response()
            # Delete tokens from cookies
            if access_token is not None:
                logger.info(
                    {
                        "event_type": EventType.LOGOUT,
                        "message": "Logout - delete access token from cookie process",
                    }
                )
                delete_auth_cookie(res, settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"])
            if refresh_token is not None:
                logger.info(
                    {
                        "event_type": EventType.LOGOUT,
                        "message": "Begin logout - delete refresh token from cookie and blacklist token process",
                    }
                )
                delete_auth_cookie(res, settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"])
                # Store deleted refresh token in blacklist
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
        except NotAuthenticated as e:
            logger.error(
                {
                    "event_type": EventType.LOGOUT,
                    "error_type": ErrorTypes.TOKEN_NOT_FOUND,
                    "error_content": str(e),
                }
            )
            raise Conflict(str(e))
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.LOGOUT,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()
