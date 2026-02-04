import logging

from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.conf import settings
from rest_framework import status
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import (
    ValidationError,
    APIException,
    NotFound,
    PermissionDenied,
)

from common.constants import ErrorTypes, EventType
from common.auth.tokens import ScopeTokenPurpose
from common.auth.authentication import configure_auth
from ..models import CustomUser, UserQuestionAnswer
from ..serializers.account_serializers import (
    CreateAccountSerializer,
    GetAccountInfoSerializer,
    SetPasswordSerializer,
    SetSecurityQASerializer,
)

logger = logging.getLogger(__name__)


class AccountViewSet(ViewSet):
    """
    Viewset for support Account related APIs
    (Create, Update, Delete)
    """

    # We will add authentication class for this api view in the future
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
            serializer = CreateAccountSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            # Set initial password and username
            response_data = {
                "username": CustomUser.generate_username_from_name(data["name"]),
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
            raise e
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.CREATE_USER_ACCOUNT,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(
        detail=False,
        methods=["get"],
        url_path="info",
        authentication_classes=[
            configure_auth(
                cookie_priority=[
                    settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"],
                    settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                ],
                use_header=True,
            )
        ],
    )
    def get_user_info(self, request):
        """
        Endpoint to get user info
        """
        try:
            logger.info(
                {
                    "event_type": EventType.GET_USER_INFO,
                    "message": "Begin retrieve user info",
                }
            )
            user = request.user
            serializer = GetAccountInfoSerializer(user)
            logger.info(
                {
                    "event_type": EventType.GET_USER_INFO,
                    "message": "Complete get user info",
                }
            )
            return JsonResponse(
                {
                    "message": "Successfully retrieve user info",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.GET_USER_INFO,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(
        detail=False,
        methods=["get"],
        url_path="setup_status",
        authentication_classes=[
            configure_auth(
                cookie_priority=[
                    settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"],
                    settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                ],
            )
        ],
    )
    def get_user_setup_status(self, request):
        """
        Endpoint to get user setup status
        (password setup status/security qa setup status)
        """
        try:
            logger.info(
                {
                    "event_type": EventType.GET_USER_SETUP_STATUS,
                    "message": "Begin retrieve user setup status",
                }
            )
            user = request.user
            user_data = {"id": user.id, "username": user.username}
            # Add user setup status if user is newly created one
            if user.is_default_password or not user.is_security_question_set:
                user_data["first_time_setup"] = True
                user_data["is_password_setup"] = not user.is_default_password
                user_data["is_security_qa_setup"] = user.is_security_question_set
            logger.info(
                {
                    "event_type": EventType.GET_USER_SETUP_STATUS,
                    "message": "Complete get user setup status",
                }
            )
            return JsonResponse(
                {"message": "Retrieve user setup status success", "data": user_data},
            )
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.GET_USER_SETUP_STATUS,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(
        detail=False,
        methods=["post"],
        url_path="password",
        authentication_classes=[
            configure_auth(
                cookie_priority=[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]],
                valid_scopes=[
                    ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                    ScopeTokenPurpose.SECURITY_QUESTION_VERIFY_SCOPE,
                ],
            )
        ],
    )
    def set_password(self, request):
        """
        Endpoint to update password
        """
        try:
            user = request.user
            logger.info(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "user_id": user.id,
                    "message": "Begin set new password process - validate request process",
                }
            )
            # Validate new password
            serializer = SetPasswordSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            logger.info(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "user_id": user.id,
                    "message": "Begin set new password process - update password process",
                }
            )
            # Set password
            user.set_password(serializer.validated_data["password"])
            if user.is_default_password:
                # If user change the password for the first time, set this flag to false
                user.is_default_password = False
            user.save()
            logger.info(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "user_id": user.id,
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
            raise e
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(
        detail=False,
        methods=["post"],
        url_path="security_qa",
        authentication_classes=[
            configure_auth(
                cookie_priority=[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]],
                valid_scopes=[ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE],
            )
        ],
    )
    def set_security_question_answer(self, request):
        """
        Endpoint to set new security question answer (for the first time/reset security question)
        """
        try:
            user = request.user
            logger.info(
                {
                    "event_type": EventType.SET_SECURITY_QA,
                    "user_id": user.id,
                    "message": "Begin set security qa process - validate request process",
                }
            )
            # Validate security qa
            serializer = SetSecurityQASerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            # Delete old security question answer of current user
            # and replace with the new one
            logger.info(
                {
                    "event_type": EventType.SET_SECURITY_QA,
                    "user_id": user.id,
                    "message": "Set new security qa",
                }
            )
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
                    "user_id": user.id,
                    "message": "Reset security qa successful",
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
            raise e
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.SET_SECURITY_QA,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()

    @action(
        detail=False,
        methods=["get"],
        url_path="security_questions/(?P<username>[^/.]+)",
    )
    def get_user_security_questions(self, request, username):
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
            user = CustomUser.objects.get(username=username)
            if not user.is_security_question_set or user.is_default_password:
                # If user has't login to setup for the first time, return error response
                logger.error(
                    {
                        "event_type": EventType.GET_USER_SECURITY_QUESTIONS,
                        "error_type": ErrorTypes.UNAUTHORIZED,
                        "error_content": f"User with username {username} hasn't setup account",
                        "is_security_question_set": user.is_security_question_set,
                        "is_default_password": user.is_default_password,
                    }
                )
                raise PermissionDenied(
                    f"User with username {username} hasn't setup account, cannot perform this action"
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
                    "data": questions_list,
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
            raise e
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.GET_USER_SECURITY_QUESTIONS,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": f"User with username {username} is not existed",
                }
            )
            raise NotFound("Account invalid or deleted")
        except PermissionDenied as e:
            raise e
        except Exception as e:
            logger.error(
                {
                    "event_type": EventType.GET_USER_SECURITY_QUESTIONS,
                    "error_type": ErrorTypes.EXCEPTION,
                    "error_content": str(e),
                }
            )
            raise APIException()
