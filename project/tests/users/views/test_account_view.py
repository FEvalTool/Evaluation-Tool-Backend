from unittest import mock
from django.contrib.auth.hashers import check_password
from django.urls import reverse
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser, SecurityQuestion, UserQuestionAnswer
from core.constants import ErrorTypes, EventType
from core.auth.tokens import ScopeTokenPurpose
from tests.helpers.setup_mock_accounts import (
    setup_mock_accounts,
    ACTIVE_USER_USERNAME,
    NEW_USER_USERNAME,
    ACTIVE_USER_PASSWORD,
    NEW_USER_PASSWORD,
)
from tests.helpers.setup_mock_token import TokenFactory
from tests.helpers.utils import get_error_key_response, CustomAPITestCase


class AccountViewsTestCase(CustomAPITestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.cookies.clear()
        self.account_url = reverse("account-list")
        self.set_password_url = reverse("account-set-password")
        self.set_security_qa_url = reverse("account-set-security-question-answer")
        self.get_user_setup_status_url = reverse("account-get-user-setup-status")
        # Set up user info for account creation tests
        self.user_info = {
            "name": "New Test User",
            "phone_number": "0392123456",
            "dob": "1990-01-01",
            "identity_number": "001234567890",
        }

        # Set up a user in the database for set password tests,
        setup_mock_accounts()
        # Get users and security questions for testing
        self.new_user = CustomUser.objects.get(username=NEW_USER_USERNAME)
        self.active_user = CustomUser.objects.get(username=ACTIVE_USER_USERNAME)
        self.security_questions = SecurityQuestion.objects.filter(
            status="Official"
        ).order_by("id")

    def generate_get_user_security_questions_url(self, username):
        return reverse(
            "account-get-user-security-questions", kwargs={"username": username}
        )

    def test_create_account_success(self):
        # Act
        response = self.client.post(self.account_url, self.user_info)
        # Assert response status + structure
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertResponseStructure(response, has_data=True)
        # Assert response body
        self.assertEqual(response.json()["message"], "Successfully intialize account")
        self.assertIn("username", response.json()["data"])
        self.assertEqual("UserNT1", response.json()["data"]["username"])
        self.assertIn("password", response.json()["data"])

    def test_create_account_validation_failure(self):
        # Arrange: invalid data
        invalid_user_info = self.user_info.copy()
        invalid_user_info["phone_number"] = "invalid_phone"
        # Act
        response = self.client.post(self.account_url, invalid_user_info)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "validation")
        error_item_keys = get_error_key_response(response)
        self.assertIn("phone_number", error_item_keys)

    @mock.patch("users.views.account_views.logger")
    @mock.patch("users.views.account_views.CustomUser.generate_username_from_name")
    def test_create_account_internal_server_error(
        self, mock_generate_username, mock_logger
    ):
        # Arrange: Mock fail function
        client = APIClient(raise_request_exception=False)
        exception_message = "Create account: Unexpected error when generate username"
        mock_generate_username.side_effect = Exception(exception_message)
        # Act
        response = client.post(self.account_url, self.user_info)
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.CREATE_USER_ACCOUNT)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_get_new_user_setup_status_success(self):
        # Arrange: Get user instance and set scope token in cookie
        user_instance = CustomUser.objects.get(username=NEW_USER_USERNAME)
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                username=NEW_USER_USERNAME,
            )
        )
        # Act
        response = self.client.get(self.get_user_setup_status_url)
        # Assert response status + structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        # Assert response body
        self.assertEqual(
            response.json()["message"], "Retrieve user setup status success"
        )
        user_data = response.json()["data"]
        self.assertEqual(user_data["username"], user_instance.username)
        self.assertEqual(user_data["first_time_setup"], True)
        self.assertEqual(user_data["is_password_setup"], False)
        self.assertEqual(user_data["is_security_qa_setup"], False)

    def test_get_active_user_setup_status_success(self):
        # Arrange: Get user instance and set access token to cookie
        user_instance = CustomUser.objects.get(username=ACTIVE_USER_USERNAME)
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"],
                username=ACTIVE_USER_USERNAME,
            )
        )
        # Act
        response = self.client.get(self.get_user_setup_status_url)
        # Assert response status + structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        # Assert response body
        self.assertEqual(
            response.json()["message"], "Retrieve user setup status success"
        )
        user_data = response.json()["data"]
        self.assertEqual(user_data["username"], user_instance.username)
        self.assertNotIn("first_time_setup", user_data)
        self.assertNotIn("is_password_setup", user_data)
        self.assertNotIn("is_security_qa_setup", user_data)

    def test_get_user_setup_status_token_not_found(self):
        # Act
        response = self.client.get(self.get_user_setup_status_url)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "not_authenticated")
        self.assertEqual(response.json()["message"], "No token provided")

    def test_get_user_setup_status_invalid_token(self):
        # Arrange: Set invalid scope token in cookie
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.invalid_signature()
        )
        # Act
        response = self.client.get(self.get_user_setup_status_url)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "authentication_failed")

    def test_get_user_setup_status_user_not_exist(self):
        # Arrange: Set unknown user token in cookie
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.unknown_user(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
            )
        )
        # Act
        response = self.client.get(self.get_user_setup_status_url)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "not_found")
        self.assertEqual(response.json()["message"], "Account invalid or deleted")

    @mock.patch("users.views.account_views.logger")
    @mock.patch("users.views.account_views.JsonResponse")
    def test_get_user_setup_status_internal_server_error(
        self, mock_json_response, mock_logger
    ):
        # Arrange: Mock fail function and set cookie
        client = APIClient(raise_request_exception=False)
        client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                username=NEW_USER_USERNAME,
            )
        )

        exception_message = (
            "Get user setup status: Unexpected error when creating json response"
        )
        mock_json_response.side_effect = Exception(exception_message)
        # Act
        response = client.get(self.get_user_setup_status_url)
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.GET_USER_SETUP_STATUS)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_set_password_success_active_user(self):
        # Assert user password before update
        self.assertTrue(check_password(ACTIVE_USER_PASSWORD, self.active_user.password))
        # Arrange: set scope token in cookie
        new_password = "NewPassword123!"
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                username=ACTIVE_USER_USERNAME,
            )
        )
        # Act
        response = self.client.post(
            self.set_password_url, {"password": "NewPassword123!"}
        )
        self.active_user.refresh_from_db()  # Refresh user data
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["message"], "Successfully set new password")
        # Assert password change success
        self.assertTrue(check_password(new_password, self.active_user.password))

    def test_set_password_success_new_user(self):
        # Assert user password before update
        self.assertTrue(check_password(NEW_USER_PASSWORD, self.new_user.password))
        self.assertTrue(self.new_user.is_default_password)
        # Arrange: set scope token in cookie
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                username=NEW_USER_USERNAME,
            )
        )
        new_password = "NewPassword123!"
        # Act
        response = self.client.post(self.set_password_url, {"password": new_password})
        self.new_user.refresh_from_db()  # Refresh user data
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["message"], "Successfully set new password")
        # Assert password change success
        self.assertFalse(self.new_user.is_default_password)
        self.assertTrue(check_password(new_password, self.new_user.password))

    def test_set_password_validation_failure(self):
        # Arrange: set scope token in cookie
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                username=NEW_USER_USERNAME,
            )
        )
        # Act
        response = self.client.post(self.set_password_url, {})
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "validation")
        error_item_keys = get_error_key_response(response)
        self.assertIn("password", error_item_keys)

    def test_set_password_token_not_found(self):
        # Act
        response = self.client.post(
            self.set_password_url,
            {"password": "NewPassword123!"},
        )
        # Check response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "not_authenticated")
        self.assertEqual(response.json()["message"], "No token provided")

    def test_set_password_invalid_token(self):
        # Arrange: set invalid scope token in cookie
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.invalid_signature()
        )
        # Act
        response = self.client.post(
            self.set_password_url,
            {"password": "NewPassword123!"},
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "authentication_failed")

    def test_set_password_user_not_exist(self):
        # Arrange: set unknown user scope token in cookie
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.unknown_user(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
            )
        )
        # Act
        response = self.client.post(
            self.set_password_url, {"password": "NewPassword123!"}
        )
        # Assert response
        self.assertEqual(response.status_code, 404)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "not_found")
        self.assertEqual(response.json()["message"], "Account invalid or deleted")

    @mock.patch("users.views.account_views.logger")
    @mock.patch("users.views.account_views.JsonResponse")
    def test_set_password_internal_server_error(self, mock_json_response, mock_logger):
        # Arrange: Mock fail function and set cookie
        client = APIClient(raise_request_exception=False)
        client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                username=NEW_USER_USERNAME,
            )
        )

        exception_message = "Set password: Unexpected error when creating json response"
        mock_json_response.side_effect = Exception(exception_message)
        # Act
        response = client.post(self.set_password_url, {"password": "NewPassword123!"})
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.SET_PASSWORD)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_set_security_qa_success_active_user(self):
        # Assert user security qa before update
        before_update_user_qa = UserQuestionAnswer.objects.filter(
            user=self.active_user.id
        ).order_by("id")
        before_update_questions = [qa.question.id for qa in before_update_user_qa]
        before_update_answers = [qa.answer for qa in before_update_user_qa]
        expect_before_update_questions = [
            question.id for question in self.security_questions[:3]
        ]
        self.assertEqual(before_update_questions, expect_before_update_questions)
        self.assertEqual(before_update_answers, ["Answer 1", "Answer 2", "Answer 3"])
        # Arrange: set scope token in cookie/security questions prepare/before change answer
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                username=ACTIVE_USER_USERNAME,
            )
        )
        question_ids = [question.id for question in self.security_questions[3:]]
        new_answers = ["New Answer 1", "New Answer 2", "New Answer 3"]
        # Act
        response = self.client.post(
            self.set_security_qa_url,
            {"questions": question_ids, "answers": new_answers},
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response)
        self.assertEqual(
            response.json()["message"],
            "Successfully set new security question and answer",
        )
        # Assert user security questions answers after update
        after_update_user_qa = UserQuestionAnswer.objects.filter(
            user=self.active_user.id
        ).order_by("id")
        after_update_questions = [qa.question.id for qa in after_update_user_qa]
        after_update_answers = [qa.answer for qa in after_update_user_qa]
        self.assertEqual(after_update_questions, question_ids)
        self.assertEqual(after_update_answers, new_answers)

    def test_security_qa_success_new_user(self):
        # Assert user security qa before update
        before_update_user_qa = UserQuestionAnswer.objects.filter(
            user=self.new_user.id
        ).order_by("id")
        self.assertEqual(len(before_update_user_qa), 0)
        # Arrange: get security qa setup status/set scope token in cookie/security questions prepare
        user_instance = CustomUser.objects.get(username=NEW_USER_USERNAME)
        before_update_security_qa_state = user_instance.is_security_question_set
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                username=NEW_USER_USERNAME,
            )
        )
        question_ids = [question.id for question in self.security_questions[3:]]
        answers = ["New Answer 1", "New Answer 2", "New Answer 3"]
        # Act
        response = self.client.post(
            self.set_security_qa_url,
            {"questions": question_ids, "answers": answers},
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response)
        self.assertIn("message", response.json())
        self.assertEqual(
            response.json()["message"],
            "Successfully set new security question and answer",
        )
        # Assert security qa setup status
        user_instance = CustomUser.objects.get(username=NEW_USER_USERNAME)
        after_update_security_qa_state = user_instance.is_default_password
        self.assertNotEqual(
            before_update_security_qa_state, after_update_security_qa_state
        )
        self.assertTrue(after_update_security_qa_state)
        # Assert user security questions answers after update
        after_update_user_qa = UserQuestionAnswer.objects.filter(
            user=self.new_user.id
        ).order_by("id")
        after_update_questions = [qa.question.id for qa in after_update_user_qa]
        after_update_answers = [qa.answer for qa in after_update_user_qa]
        self.assertEqual(after_update_questions, question_ids)
        self.assertEqual(after_update_answers, answers)

    def test_set_security_qa_validation_failure(self):
        # Arrange: set scope token in cookie/security questions prepare
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                username=NEW_USER_USERNAME,
            )
        )
        # Act
        response = self.client.post(
            self.set_security_qa_url,
            {},
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "validation")
        error_item_keys = get_error_key_response(response)
        self.assertIn("questions", error_item_keys)
        self.assertIn("answers", error_item_keys)

    def test_set_security_qa_token_not_found(self):
        # Arrange: security questions prepare
        question_ids = [question.id for question in self.security_questions[:3]]
        answers = ["New Answer 1", "New Answer 2", "New Answer 3"]
        # Act
        response = self.client.post(
            self.set_security_qa_url,
            {"questions": question_ids, "answers": answers},
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "not_authenticated")
        self.assertEqual(response.json()["message"], "No token provided")

    def test_set_security_qa_invalid_token(self):
        # Arrange: set invalid scope token in cookie/security questions prepare
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.invalid_signature()
        )
        question_ids = [question.id for question in self.security_questions[:3]]
        answers = ["New Answer 1", "New Answer 2", "New Answer 3"]
        # Act
        response = self.client.post(
            self.set_security_qa_url,
            {"questions": question_ids, "answers": answers},
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "authentication_failed")

    def test_set_security_qa_user_not_exist(self):
        # Arrange: set invalid scope token in cookie/security questions prepare
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.unknown_user(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
            )
        )
        question_ids = [question.id for question in self.security_questions[:3]]
        answers = ["New Answer 1", "New Answer 2", "New Answer 3"]
        # Act
        response = self.client.post(
            self.set_security_qa_url,
            {"questions": question_ids, "answers": answers},
        )
        # Assert response
        self.assertEqual(response.status_code, 404)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "not_found")
        self.assertEqual(response.json()["message"], "Account invalid or deleted")

    @mock.patch("users.views.account_views.logger")
    @mock.patch("users.views.account_views.JsonResponse")
    def test_set_security_qa_internal_server_error(
        self, mock_json_response, mock_logger
    ):
        # Arrange: Mock fail function/security questions prepare and set cookie
        client = APIClient(raise_request_exception=False)
        client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=ScopeTokenPurpose.PASSWORD_VERIFY_SCOPE,
                username=NEW_USER_USERNAME,
            )
        )

        exception_message = (
            "Set security qa: Unexpected error when creating json response"
        )
        mock_json_response.side_effect = Exception(exception_message)
        question_ids = [question.id for question in self.security_questions[:3]]
        answers = ["New Answer 1", "New Answer 2", "New Answer 3"]
        # Act
        response = client.post(
            self.set_security_qa_url,
            {"questions": question_ids, "answers": answers},
        )
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.SET_SECURITY_QA)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_get_user_security_questions_success(self):
        # Act
        response = self.client.get(
            self.generate_get_user_security_questions_url(ACTIVE_USER_USERNAME)
        )
        # Assert response status + structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        # Assert response body
        self.assertEqual(
            response.json()["message"], "Retrieve user security questions successful"
        )
        self.assertEqual(len(response.json()["data"]), 3)
        for question in response.json()["data"]:
            self.assertIn("content", question)
            self.assertIn("id", question)

    def test_get_user_security_questions_new_user_not_allowed(self):
        # Act
        response = self.client.get(
            self.generate_get_user_security_questions_url(NEW_USER_USERNAME)
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "permission_denied")
        self.assertEqual(
            response.json()["message"],
            f"User with username {NEW_USER_USERNAME} hasn't setup account, cannot perform this action",
        )

    def test_get_user_security_questions_username_not_exist(self):
        # Act
        response = self.client.get(
            self.generate_get_user_security_questions_url("unknownuser")
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "not_found")
        self.assertEqual(response.json()["message"], "Account invalid or deleted")

    @mock.patch("users.views.account_views.logger")
    @mock.patch("users.views.account_views.CustomUser.objects.get")
    def test_get_user_security_questions_internal_server_error(
        self, mock_get_user, mock_logger
    ):
        # Arrange: Mock fail function
        client = APIClient(raise_request_exception=False)
        exception_message = (
            "Get user security questions: Unexpected error when retrieving user"
        )
        mock_get_user.side_effect = Exception(exception_message)
        # Act
        response = client.get(
            self.generate_get_user_security_questions_url(ACTIVE_USER_USERNAME)
        )
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(
            logged_data["event_type"], EventType.GET_USER_SECURITY_QUESTIONS
        )
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")
