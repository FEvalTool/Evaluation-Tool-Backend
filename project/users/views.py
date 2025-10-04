from django.http import JsonResponse
from django.utils.crypto import get_random_string

from rest_framework import status, serializers
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

import logging

from .models import CustomUser, UserQuestionAnswer
from .serializers import (
    InitAccountSerializer,
    UserLoginSerializer,
    SetPasswordSerializer,
    SetSecurityQASerializer,
    GetSecurityQuestionParamsSerializer,
    GetSecurityQAVerificationTokenSerializer,
)
from common.constants import ErrorTypes
from .constants import EventType, TokenScope
from .exceptions import TokenValidationException, SecurityQAValidationException
from .utils import (
    generate_username,
    create_jwt,
    decode_and_verify_jwt,
    verify_is_able_to_set_password,
    verify_is_able_to_set_security_qa,
)

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
                {"message": "Successfully intialize account", "data": response_data}
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
                    "error-content": e.detail,
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
                {
                    "message": "Internal server error",
                    "error-content": "An unexpected error occurred.",
                },
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
            serializer = SetPasswordSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            payload = decode_and_verify_jwt(
                serializer.validated_data["token"], verify_is_able_to_set_password
            )
            user = CustomUser.objects.get(username=payload["username"])
            user.set_password(serializer.validated_data["password"])
            if user.is_default_password:
                # If user change the password for the first time, set this flag to false
                user.is_default_password = False
            user.save()
            logger.info(
                {
                    "event_type": EventType.SET_PASSWORD,
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
                    "error-content": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TokenValidationException as e:
            logger.error(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "error_type": ErrorTypes.TOKEN_VALIDATION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Token validation failed", "error-content": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.SET_PASSWORD,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": f"User with username {payload['username']} does not found",
                }
            )
            return JsonResponse(
                {"message": f"User with username {payload['username']} does not found"},
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
                {
                    "message": "Internal server error",
                    "error-content": "An unexpected error occurred.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"], url_path="security_questions")
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
            serializer = SetSecurityQASerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            payload = decode_and_verify_jwt(
                serializer.validated_data["token"], verify_is_able_to_set_security_qa
            )
            # Delete old security question answer of current user
            # and replace with the new one
            logger.info(
                {
                    "event_type": EventType.SET_SECURITY_QA,
                    "message": "Reset security question if exist",
                }
            )
            user = CustomUser.objects.get(username=payload["username"])
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
                    "error-content": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TokenValidationException as e:
            logger.error(
                {
                    "event_type": EventType.SET_SECURITY_QA,
                    "error_type": ErrorTypes.TOKEN_VALIDATION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Token validation failed", "error-content": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.SET_SECURITY_QA,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": f"User with username {payload['username']} does not found",
                }
            )
            return JsonResponse(
                {"message": f"User with username {payload['username']} does not found"},
                status=status.HTTP_404_NOT_FOUND,
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
                {
                    "message": "Internal server error",
                    "error-content": "An unexpected error occurred.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"], url_path="security_questions")
    def get_user_security_question(self, request):
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
                    {"message": f"User {username} has't setup account"},
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
                    "messages": "Retrieve user security questions successful",
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
                    "error-content": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.GET_USER_SECURITY_QUESTIONS,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": f"User with username {username} does not found",
                }
            )
            return JsonResponse(
                {"message": f"User with username {username} does not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


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
                "access_token": create_jwt(
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
                    "error_content": e.detail,
                }
            )
            return JsonResponse(
                {
                    "message": "Invalid request",
                    "error_type": ErrorTypes.REQUEST_VALIDATION,
                    "error-content": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.LOGIN,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": "Username or password is incorrect",
                }
            )
            return JsonResponse(
                {"message": "Username or password is incorrect"},
                status=status.HTTP_404_NOT_FOUND,
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
                {
                    "message": "Internal server error",
                    "error-content": "An unexpected error occurred.",
                },
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
                    "event_type": EventType.GENERATE_SECURITY_QA_VERIFICATION_TOKEN,
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
                        "event_type": EventType.GENERATE_SECURITY_QA_VERIFICATION_TOKEN,
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
            userQA = UserQuestionAnswer.objects.filter(
                user_id=user.id, question_id__in=question_ids
            )
            if not userQA.count() == len(serializer.validated_data["questions"]):
                raise serializers.ValidationError(
                    {"questions": ["User security questions doesn't existed"]}
                )
            correct_answers = [userQA.get(question_id=id).answer for id in question_ids]
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
                    "event_type": EventType.GENERATE_SECURITY_QA_VERIFICATION_TOKEN,
                    "message": "Get security qa verification token successfully",
                    "username": username,
                }
            )

            return JsonResponse(
                {
                    "message": "Successfully Retrieve Security QA token",
                    "token": token,
                },
            )

        except ValidationError as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_SECURITY_QA_VERIFICATION_TOKEN,
                    "error_content": e.detail,
                }
            )
            return JsonResponse(
                {
                    "message": "Invalid request",
                    "error_type": ErrorTypes.REQUEST_VALIDATION,
                    "error-content": e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.GENERATE_SECURITY_QA_VERIFICATION_TOKEN,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": "Username is not existed",
                }
            )
            return JsonResponse(
                {"message": "Username is not existed"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except SecurityQAValidationException as e:
            logger.error(
                {
                    "event_type": EventType.GENERATE_SECURITY_QA_VERIFICATION_TOKEN,
                    "error_type": ErrorTypes.SECURITY_QA_VALIDATION,
                    "error_content": str(e),
                }
            )
            return JsonResponse(
                {"message": "Security QA validation failed", "error-content": str(e)},
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
                {
                    "message": "Internal server error",
                    "error-content": "An unexpected error occurred.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
