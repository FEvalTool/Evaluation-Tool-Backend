import time
from unittest import mock
from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from users.models import UserQuestionAnswer
from users.constants import TokenScope, BYPASS_TOKEN_NOTFOUND, EventType
from common.constants import ErrorTypes
from users.redis.tokens import RefreshTokenRedis, ScopeTokenRedis
from tests.helpers.setup_mock_accounts import (
    setup_mock_accounts,
    ACTIVE_USER_USERNAME,
    NEW_USER_USERNAME,
    ACTIVE_USER_PASSWORD,
    NEW_USER_PASSWORD,
)
from tests.helpers.setup_mock_token import TokenFactory, get_jti_from_jwt
from tests.helpers.utils import get_error_key_response, CustomAPITestCase


class AuthViewsTestCase(CustomAPITestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.cookies.clear()
        self.login_url = reverse("auth-login")
        self.generate_qa_token_url = reverse(
            "auth-generate-question-answer-verification-token"
        )
        self.generate_password_token_url = reverse(
            "auth-generate-password-verification-token"
        )
        self.verify_token_url = reverse("auth-verify-token")
        self.refresh_token_url = reverse("auth-refresh-token")
        self.delete_scope_token_url = reverse("auth-delete-scope-token")
        self.logout_url = reverse("auth-delete-refresh-access-token")
        setup_mock_accounts()

    def test_login_success_new_user(self):
        # Arrange expected scope token expire time
        now = int(time.time())
        expected_token_expiry = (now + (10 * 60)) * 1000  # 10 minute expire scope token
        # Act
        response = self.client.post(
            self.login_url,
            {"username": NEW_USER_USERNAME, "password": NEW_USER_PASSWORD},
            format="json",
        )
        # Assert response status + structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        # Assert response body - message
        self.assertEqual("Successfully Login", response.json()["message"])
        # Assert response body - user data
        self.assertIn("user", response.json()["data"])
        user_data = response.json()["data"]["user"]
        self.assertEqual(user_data["username"], NEW_USER_USERNAME)
        self.assertEqual(user_data["first_time_setup"], True)
        self.assertEqual(user_data["is_password_setup"], False)
        self.assertEqual(user_data["is_security_qa_setup"], False)
        # Assert response body - scope token expire time
        self.assertIn("scope_token_exp", response.json()["data"])
        scope_token_exp = response.json()["data"]["scope_token_exp"]
        self.assertAlmostEqual(
            scope_token_exp,
            expected_token_expiry,
            delta=5000,  # 5 seconds delay
        )
        # Assert scope token generate in cookie
        scope_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]
        )
        self.assertIsNotNone(
            scope_token_cookie,
            f"The {settings.COOKIE_SETTINGS['AUTH_COOKIE_SCOPE']} cookie was not set in the response.",
        )

    def test_login_success_active_user(self):
        # Act
        response = self.client.post(
            self.login_url,
            {"username": ACTIVE_USER_USERNAME, "password": ACTIVE_USER_PASSWORD},
            format="json",
        )
        # Assert response status + structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        # Assert response body - message
        self.assertEqual("Successfully Login", response.json()["message"])
        # Assert response body
        self.assertIn("user", response.json()["data"])
        self.assertNotIn("scope_token_exp", response.json()["data"])
        user_data = response.json()["data"]["user"]
        self.assertEqual(user_data["username"], ACTIVE_USER_USERNAME)
        with self.assertRaises(KeyError) as context:
            _ = user_data["first_time_setup"]
        # Assert scope token generate in cookie
        scope_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]
        )
        self.assertIsNotNone(
            scope_token_cookie,
            f"The {settings.COOKIE_SETTINGS['AUTH_COOKIE_ACCESS']} cookie was not set in the response.",
        )
        scope_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]
        )
        self.assertIsNotNone(
            scope_token_cookie,
            f"The {settings.COOKIE_SETTINGS['AUTH_COOKIE_REFRESH']} cookie was not set in the response.",
        )

    def test_login_failure_wrong_password(self):
        # Act
        response = self.client.post(
            self.login_url,
            {"username": NEW_USER_USERNAME, "password": "wrongpassword"},
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "authentication_failed")
        self.assertEqual(response.json()["message"], "Invalid username or password")

    def test_login_validation_failure(self):
        # Act
        response = self.client.post(
            self.login_url,
            {"username": NEW_USER_USERNAME},
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "validation")
        error_item_keys = get_error_key_response(response)
        self.assertIn("password", error_item_keys)

    @mock.patch("users.views.auth_views.logger")
    @mock.patch("users.views.auth_views.ScopeToken.for_user")
    def test_login_internal_server_error(self, mock_create_jwt, mock_logger):
        # Arrange: Mock fail function
        client = APIClient(raise_request_exception=False)
        exception_message = "Login: Unexpected error when creating JWT"
        mock_create_jwt.side_effect = Exception(exception_message)
        # Act
        response = client.post(
            self.login_url,
            {"username": NEW_USER_USERNAME, "password": NEW_USER_PASSWORD},
            content_type="application/json",
        )
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.LOGIN)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_generate_qa_verification_token_success(self):
        # Arrange security questions and answers/expected mock token expired time
        questions_answers = UserQuestionAnswer.objects.all()
        questions = [qa.question.id for qa in questions_answers]
        answers = [qa.answer for qa in questions_answers]
        now = int(time.time())
        expected_token_expiry = (now + (10 * 60)) * 1000  # 10 minute expire scope token
        # Act
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": ACTIVE_USER_USERNAME,
                "questions": questions,
                "answers": answers,
            },
            format="json",
        )

        # Assert response status + structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        # Assert response body - message
        self.assertEqual(response.json()["message"], "Token generated successfully")
        # Assert response body - scope token expire time
        self.assertIn("scope_token_exp", response.json()["data"])
        self.assertAlmostEqual(
            response.json()["data"]["scope_token_exp"],
            expected_token_expiry,
            delta=5000,  # 5 seconds delay
        )
        # Assert token generated in cookie
        scope_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]
        )
        self.assertIsNotNone(
            scope_token_cookie,
            f"The {settings.COOKIE_SETTINGS['AUTH_COOKIE_SCOPE']} cookie was not set in the response.",
        )

    def test_generate_qa_verification_token_new_user_not_allowed(self):
        # Act
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": NEW_USER_USERNAME,
                "questions": [1, 2, 3],
                "answers": ["answer", "answer", "answer"],
            },
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "permission_denied")
        self.assertEqual(
            response.json()["message"],
            f"User with username {NEW_USER_USERNAME} hasn't setup account, cannot perform this action",
        )

    def test_generate_qa_verification_token_wrong_answer_failure(self):
        # Arrange security questions
        questions_answers = UserQuestionAnswer.objects.all()
        questions = [qa.question.id for qa in questions_answers]
        # Act
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": ACTIVE_USER_USERNAME,
                "questions": questions,
                "answers": ["Wrong1", "Wrong2", "Wrong3"],
            },
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "authentication_failed")
        self.assertEqual(
            response.json()["message"], "Invalid security credentials provided"
        )

    def test_generate_qa_verification_user_not_found(self):
        # Act
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": "unknownuser",
                "questions": [1, 2, 3],
                "answers": ["answer", "answer", "answer"],
            },
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "authentication_failed")
        self.assertEqual(
            response.json()["message"], "Invalid security credentials provided"
        )

    def test_generate_qa_verification_token_validation_failure(self):
        # Act
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": ACTIVE_USER_USERNAME,
                "questions": [1, 2],
                "answers": ["Fluffy", "Smith"],
            },
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "validation")
        error_item_keys = get_error_key_response(response)
        self.assertIn("questions", error_item_keys)
        self.assertIn("answers", error_item_keys)

    def test_generate_qa_verification_token_question_not_exist(self):
        # Arrange security questions with unknown question
        questions_answers = UserQuestionAnswer.objects.all()
        questions = [qa.question.id for qa in questions_answers]
        questions.pop()
        questions.append(9999)
        # Act
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": ACTIVE_USER_USERNAME,
                "questions": questions,
                "answers": ["Answer", "Answer", "Answer"],
            },
            format="json",
        )
        # Assert response status + structure
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertResponseStructure(response)
        # Assert response body
        self.assertEqual(response.json()["code"], "validation")
        error_item_keys = get_error_key_response(response)
        self.assertIn("questions", error_item_keys)
        questions_val_err = [
            error
            for error in response.json()["error"]
            if list(error.keys())[0] == "questions"
        ]
        questions_val_err_content = questions_val_err[0]["questions"]
        self.assertEqual(
            questions_val_err_content, "User security questions doesn't existed"
        )

    @mock.patch("users.views.auth_views.logger")
    @mock.patch("users.views.auth_views.ScopeToken.for_user")
    def test_generate_qa_verification_token_internal_server_error(
        self, mock_create_jwt, mock_logger
    ):
        # Arrange: Mock fail function and security questions/answers
        client = APIClient(raise_request_exception=False)
        exception_message = (
            "Gen QA verification token: Unexpected error when creating JWT"
        )
        mock_create_jwt.side_effect = Exception(exception_message)
        questions_answers = UserQuestionAnswer.objects.all()
        questions = [qa.question.id for qa in questions_answers]
        answers = [qa.answer for qa in questions_answers]
        # Act
        response = client.post(
            self.generate_qa_token_url,
            {
                "username": ACTIVE_USER_USERNAME,
                "questions": questions,
                "answers": answers,
            },
            format="json",
        )
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(
            logged_data["event_type"], EventType.GENERATE_VERIFICATION_TOKEN
        )
        self.assertEqual(
            logged_data["scope"], TokenScope.SECURITY_QUESTION_VERIFY_SCOPE
        )
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_generate_password_verification_token_success(self):
        # Arrange expected scope token expire time
        now = int(time.time())
        expected_token_expiry = (now + (10 * 60)) * 1000  # 10 minute expire scope token
        # Act
        response = self.client.post(
            self.generate_password_token_url,
            {"username": ACTIVE_USER_USERNAME, "password": ACTIVE_USER_PASSWORD},
            format="json",
        )
        # Assert response status + structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        # Assert response body - message
        self.assertEqual(response.json()["message"], "Token generated successfully")
        # Assert response body - scope token expire time
        self.assertIn("scope_token_exp", response.json()["data"])
        self.assertAlmostEqual(
            response.json()["data"]["scope_token_exp"],
            expected_token_expiry,
            delta=5000,  # 5 seconds delay
        )
        # Assert token in cookie
        scope_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]
        )
        self.assertIsNotNone(
            scope_token_cookie,
            f"The {settings.COOKIE_SETTINGS['AUTH_COOKIE_SCOPE']} cookie was not set in the response.",
        )

    def test_generate_password_verification_token_new_user_not_allowed(self):
        # Act
        response = self.client.post(
            self.generate_password_token_url,
            {"username": NEW_USER_USERNAME, "password": NEW_USER_PASSWORD},
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "permission_denied")
        self.assertEqual(
            response.json()["message"],
            f"User with username {NEW_USER_USERNAME} hasn't setup account, cannot perform this action",
        )

    def test_generate_password_verification_token_wrong_password_failure(self):
        # Act
        response = self.client.post(
            self.generate_password_token_url,
            {"username": ACTIVE_USER_USERNAME, "password": "wrongpassword"},
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "authentication_failed")
        self.assertEqual(
            response.json()["message"], "Invalid security credentials provided"
        )

    def test_generate_password_verification_token_unknown_user(self):
        # Act
        response = self.client.post(
            self.generate_password_token_url,
            {"username": "unknownuser", "password": "wrongpassword"},
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "authentication_failed")
        self.assertEqual(
            response.json()["message"], "Invalid security credentials provided"
        )

    def test_generate_password_verification_token_validation_failure(self):
        # Act
        response = self.client.post(
            self.generate_password_token_url,
            {"username": ACTIVE_USER_USERNAME},
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "validation")
        error_item_keys = get_error_key_response(response)
        self.assertIn("password", error_item_keys)

    @mock.patch("users.views.auth_views.logger")
    @mock.patch("users.views.auth_views.ScopeToken.for_user")
    def test_generate_password_verification_token_internal_server_error(
        self, mock_create_jwt, mock_logger
    ):
        # Arrange: Mock fail function
        client = APIClient(raise_request_exception=False)
        exception_message = (
            "Gen password verification token: Unexpected error when creating JWT"
        )
        mock_create_jwt.side_effect = Exception(exception_message)
        # Act
        response = client.post(
            self.generate_password_token_url,
            {"username": ACTIVE_USER_USERNAME, "password": ACTIVE_USER_PASSWORD},
            format="json",
        )
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(
            logged_data["event_type"], EventType.GENERATE_VERIFICATION_TOKEN
        )
        self.assertEqual(logged_data["scope"], TokenScope.PASSWORD_VERIFY_SCOPE)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_verify_token_success(self):
        # Arrange scope token store in cookie
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=TokenScope.PASSWORD_VERIFY_SCOPE,
                username=ACTIVE_USER_USERNAME,
            )
        )
        # Act
        response = self.client.post(
            self.verify_token_url,
            {"token_type": "scope"},
            format="json",
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["message"], "Token is valid")

    def test_verify_token_validation_failure(self):
        # Act
        response = self.client.post(self.verify_token_url, {}, format="json")
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "validation")
        error_item_keys = get_error_key_response(response)
        self.assertIn("token_type", error_item_keys)

    def test_verify_token_token_not_found(self):
        # Act
        response = self.client.post(
            self.verify_token_url, {"token_type": "scope"}, format="json"
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "not_authenticated")
        self.assertTrue("Token not found in cookie" in response.json()["message"])

    def test_verify_token_token_invalid(self):
        # Arrange invalid scope token store in cookie
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.invalid_signature()
        )
        # Act
        response = self.client.post(
            self.verify_token_url, {"token_type": "scope"}, format="json"
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "authentication_failed")

    @mock.patch("users.views.auth_views.logger")
    @mock.patch("users.views.auth_views.get_token_from_cookie")
    def test_verify_token_exception(self, mock_get_token, mock_logger):
        # Arrange: Mock fail function
        client = APIClient(raise_request_exception=False)
        exception_message = "Verify token: Unexpected error when retrieve token"
        mock_get_token.side_effect = Exception(exception_message)
        # Act
        response = client.post(
            self.verify_token_url, {"token_type": "scope"}, format="json"
        )
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.VERIFY_TOKEN)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_refresh_token_success(self):
        # Arrange refresh token store in cookie
        refresh_token = TokenFactory.valid_token(
            token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"],
            username=ACTIVE_USER_USERNAME,
        )
        jti = get_jti_from_jwt(refresh_token)  # Get before update refresh token jti
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]] = (
            refresh_token
        )
        # Act
        response = self.client.post(self.refresh_token_url)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["message"], "Refresh token successful")
        # Assert if new access token generated ok
        access_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]
        )
        self.assertIsNotNone(
            access_token_cookie,
            f"The {settings.COOKIE_SETTINGS['AUTH_COOKIE_ACCESS']} cookie was not set in the response.",
        )
        # Assert if new refresh token generated ok
        new_jti = get_jti_from_jwt(
            response.cookies.get(settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]).value
        )
        self.assertNotEqual(jti, new_jti)
        # Assert if old refresh token store in blacklist
        self.assertTrue(RefreshTokenRedis.exists(jti))

    def test_refresh_token_token_not_found(self):
        # Act
        response = self.client.post(self.refresh_token_url)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "not_authenticated")
        self.assertTrue("Token not found in cookie" in response.json()["message"])

    def test_refresh_token_token_invalid(self):
        # Arrange invalid refresh token
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]] = (
            TokenFactory.invalid_signature()
        )
        # Act
        response = self.client.post(self.refresh_token_url)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "authentication_failed")

    @mock.patch("users.views.auth_views.logger")
    @mock.patch("users.views.auth_views.get_token_from_cookie")
    def test_refresh_token_exception(self, mock_get_token, mock_logger):
        # Arrange: Mock fail function
        client = APIClient(raise_request_exception=False)
        exception_message = "Refresh token: Unexpected error when retrieve token"
        mock_get_token.side_effect = Exception(exception_message)
        # Act
        response = client.post(self.refresh_token_url)
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.REFRESH_TOKEN)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_delete_scope_token_success(self):
        # Arrange scope token store in cookie
        scope_token = TokenFactory.valid_token(
            token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
            scope=TokenScope.PASSWORD_VERIFY_SCOPE,
            username=ACTIVE_USER_USERNAME,
        )
        jti = get_jti_from_jwt(scope_token)  # Get before-deleted scope token jti
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = scope_token
        # Act
        response = self.client.post(self.delete_scope_token_url)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response)
        self.assertEqual(
            response.json()["message"], "Scope tokens deleted successfully"
        )
        # Assert if scope token in cookie is deleted
        # (Behind the scence: create new cookie but expired: Set-Cookie: scope=""; Max-Age=0; Path=/;)
        cookie = response.cookies.get(settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"])
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, "")
        self.assertEqual(cookie["max-age"], 0)
        # Assert if old scope token store in blacklist
        self.assertTrue(ScopeTokenRedis.exists(jti))

    def test_delete_scope_token_token_not_found(self):
        # Act
        response = self.client.post(
            self.delete_scope_token_url, {BYPASS_TOKEN_NOTFOUND: False}, format="json"
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "conflict")
        self.assertTrue("Token not found in cookie" in response.json()["message"])

    @mock.patch("users.views.auth_views.logger")
    @mock.patch("users.views.auth_views.get_token_from_cookie")
    def test_delete_scope_token_exception(self, mock_get_token, mock_logger):
        # Arrange: Mock fail function
        client = APIClient(raise_request_exception=False)
        exception_message = "Delete scope token: Unexpected error when retrieve token"
        mock_get_token.side_effect = Exception(exception_message)
        # Act
        response = client.post(self.delete_scope_token_url)
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.DELETE_SCOPE_TOKEN)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_logout_success(self):
        # Arrange access aand refresh token store in cookie
        refresh_token = TokenFactory.valid_token(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"],
            username=ACTIVE_USER_USERNAME,
        )
        access_token = TokenFactory.valid_token(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"],
            username=ACTIVE_USER_USERNAME,
        )
        jti = get_jti_from_jwt(refresh_token)  # Get before-deleted refresh token jti
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]] = (
            refresh_token
        )
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]] = (
            access_token
        )
        # Act
        response = self.client.post(self.logout_url)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["message"], "Logout successfully")
        # Assert if access and refresh token in cookie are deleted
        access_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]
        )
        refresh_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]
        )
        self.assertIsNotNone(access_token_cookie)
        self.assertEqual(access_token_cookie.value, "")
        self.assertEqual(access_token_cookie["max-age"], 0)
        self.assertIsNotNone(refresh_token_cookie)
        self.assertEqual(refresh_token_cookie.value, "")
        self.assertEqual(refresh_token_cookie["max-age"], 0)
        # Assert if old refresh token is store in blacklist
        self.assertTrue(RefreshTokenRedis.exists(jti))

    def test_logout_token_not_found(self):
        # Act
        response = self.client.post(
            self.logout_url, {BYPASS_TOKEN_NOTFOUND: False}, format="json"
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "conflict")
        self.assertTrue("Token not found in cookie" in response.json()["message"])

    @mock.patch("users.views.auth_views.logger")
    @mock.patch("users.views.auth_views.get_token_from_cookie")
    def test_logout_exception(self, mock_get_token, mock_logger):
        # Arrange: Mock fail function
        client = APIClient(raise_request_exception=False)
        exception_message = "Logout: Unexpected error when retrieve token"
        mock_get_token.side_effect = Exception(exception_message)
        # Act
        response = client.post(self.logout_url)
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.LOGOUT)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")
