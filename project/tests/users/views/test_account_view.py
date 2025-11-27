from unittest import mock
from django.urls import reverse
from django.conf import settings
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.constants import TokenScope
from users.models import CustomUser
from tests.helpers.setup_mock_accounts import setup_mock_accounts
from tests.helpers.setup_mock_token import TokenFactory


class AccountViewsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.cookies.clear()
        self.account_url = reverse("account-list")
        self.set_password_url = reverse("account-set-password")
        self.get_user_security_questions_url = reverse(
            "account-get-user-security-questions"
        )
        # Set up user info for account creation tests
        self.user_info = {
            "name": "New User",
            "phone_number": "0392123456",
            "dob": "1990-01-01",
            "identity_number": "001234567890",
        }

        # Set up a user in the database for set password tests,
        setup_mock_accounts()

    def test_create_account_success(self):
        response = self.client.post(self.account_url, self.user_info)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Successfully intialize account")
        self.assertIn("data", response.json())
        self.assertIn("username", response.json()["data"])
        self.assertIn("password", response.json()["data"])

    def test_create_account_validation_failure(self):
        invalid_user_info = self.user_info.copy()
        invalid_user_info["phone_number"] = "invalid_phone"

        response = self.client.post(self.account_url, invalid_user_info)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid request")
        self.assertIn("error_content", response.json())

    @mock.patch("users.views.account_views.generate_username")
    def test_create_account_internal_server_error(self, mock_generate_username):
        mock_generate_username.side_effect = Exception("Unexpected error")

        response = self.client.post(self.account_url, self.user_info)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())

    def test_set_password_success(self):
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=TokenScope.PASSWORD_VERIFY_SCOPE,
            )
        )
        response = self.client.post(
            self.set_password_url, {"password": "NewPassword123!"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Successfully set new password")

    def test_set_password_success_first_time_user(self):
        user_instance = CustomUser.objects.get(username="testuser")
        before_update_password_state = user_instance.is_default_password
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=TokenScope.PASSWORD_VERIFY_SCOPE,
                username="testuser",
            )
        )
        response = self.client.post(
            self.set_password_url, {"password": "NewPassword123!"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Successfully set new password")
        user_instance = CustomUser.objects.get(username="testuser")
        after_update_password_state = user_instance.is_default_password
        self.assertNotEqual(before_update_password_state, after_update_password_state)
        self.assertFalse(after_update_password_state)

    def test_set_password_validation_failure(self):
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=TokenScope.PASSWORD_VERIFY_SCOPE,
            )
        )
        response = self.client.post(self.set_password_url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid request")
        self.assertIn("error_content", response.json())

    def test_set_password_token_not_found(self):
        response = self.client.post(
            self.set_password_url,
            {"password": "NewPassword123!"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertTrue("Token not found in cookie" in response.json()["message"])

    def test_set_password_invalid_token(self):
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.invalid_signature()
        )
        response = self.client.post(
            self.set_password_url,
            {"password": "NewPassword123!"},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid token")
        self.assertIn("error_content", response.json())

    def test_set_password_username_not_exist(self):
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.unknown_user(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=TokenScope.PASSWORD_VERIFY_SCOPE,
            )
        )
        response = self.client.post(
            self.set_password_url, {"password": "NewPassword123!"}
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "User is not existed")

    @mock.patch("users.views.account_views.get_token_from_cookie")
    def test_set_password_internal_server_error(self, mock_get_token):
        mock_get_token.side_effect = Exception("Unexpected error")
        response = self.client.post(
            self.set_password_url, {"password": "NewPassword123!"}
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())

    def test_get_user_security_questions_success(self):
        response = self.client.get(
            self.get_user_security_questions_url, {"username": "testuser1"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(
            response.json()["message"], "Retrieve user security questions successful"
        )
        self.assertIn("questions", response.json())
        self.assertEqual(len(response.json()["questions"]), 3)
        for question in response.json()["questions"]:
            self.assertIn("content", question)
            self.assertIn("id", question)

    def test_get_user_security_questions_first_time_user_not_allowed(self):
        response = self.client.get(
            self.get_user_security_questions_url, {"username": "testuser"}
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(
            response.json()["message"], "User testuser hasn't setup account"
        )

    def test_get_user_security_questions_username_not_exist(self):
        response = self.client.get(
            self.get_user_security_questions_url, {"username": "unknownuser"}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("message", response.json())
        self.assertEqual(
            response.json()["message"], "User with username unknownuser is not existed"
        )

    def test_get_user_security_questions_validation_failure(self):
        response = self.client.get(self.get_user_security_questions_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid request")
        self.assertIn("error_content", response.json())

    @mock.patch("users.views.account_views.CustomUser.objects.get")
    def test_get_user_security_questions_internal_server_error(self, mock_get_user):
        mock_get_user.side_effect = Exception("Unexpected error")
        response = self.client.get(
            self.get_user_security_questions_url, {"username": "testuser1"}
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())
