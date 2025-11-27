from unittest import mock
from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from users.models import UserQuestionAnswer
from users.constants import TokenScope, BYPASS_TOKEN_NOTFOUND
from users.redis.tokens import RefreshTokenRedis, ScopeTokenRedis
from tests.helpers.setup_mock_accounts import setup_mock_accounts
from tests.helpers.setup_mock_token import TokenFactory, get_jti_from_jwt


class AuthViewsTestCase(TestCase):
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

    def test_login_success_first_time_setup_user(self):
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "correctpassword"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_data = response.json()["user"]
        self.assertEqual(user_data["username"], "testuser")
        self.assertEqual(user_data["first_time_setup"], True)
        self.assertEqual(user_data["is_password_setup"], False)
        self.assertEqual(user_data["is_security_qa_setup"], False)
        scope_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]
        )
        self.assertIsNotNone(
            scope_token_cookie,
            f"The {settings.COOKIE_SETTINGS['AUTH_COOKIE_SCOPE']} cookie was not set in the response.",
        )

    def test_login_success_normal_user(self):
        response = self.client.post(
            self.login_url,
            {"username": "testuser1", "password": "cORRectPassw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_data = response.json()["user"]
        self.assertEqual(user_data["username"], "testuser1")
        with self.assertRaises(KeyError) as context:
            _ = user_data["first_time_setup"]
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
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "wrongpassword"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid username or password")

    def test_login_validation_failure(self):
        response = self.client.post(
            self.login_url,
            {"username": "testuser"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid request")
        self.assertIn("error_content", response.json())
        self.assertIn("password", response.json()["error_content"])

    @mock.patch("users.views.auth_views.ScopeToken.for_user")
    def test_login_internal_server_error(self, mock_create_jwt):
        mock_create_jwt.side_effect = Exception("JWT creation failed")
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "correctpassword"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())

    def test_generate_qa_verification_token_success(self):
        questions_answers = UserQuestionAnswer.objects.all()
        questions = [qa.question.id for qa in questions_answers]
        answers = [qa.answer for qa in questions_answers]
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": "testuser1",
                "questions": questions,
                "answers": answers,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Token generated successfully")
        scope_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]
        )
        self.assertIsNotNone(
            scope_token_cookie,
            f"The {settings.COOKIE_SETTINGS['AUTH_COOKIE_SCOPE']} cookie was not set in the response.",
        )

    def test_generate_qa_verification_token_first_time_user_not_allowed(self):
        questions_answers = UserQuestionAnswer.objects.all()
        questions = [qa.question.id for qa in questions_answers]
        answers = [qa.answer for qa in questions_answers]
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": "testuser",
                "questions": questions,
                "answers": answers,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(
            response.json()["message"], "User testuser hasn't setup account"
        )

    def test_generate_qa_verification_token_wrong_answer_failure(self):
        questions_answers = UserQuestionAnswer.objects.all()
        questions = [qa.question.id for qa in questions_answers]
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": "testuser1",
                "questions": questions,
                "answers": ["Wrong1", "Wrong2", "Wrong3"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Security QA validation failed")

    def test_generate_qa_verification_username_not_found(self):
        questions_answers = UserQuestionAnswer.objects.all()
        questions = [qa.question.id for qa in questions_answers]
        answers = [qa.answer for qa in questions_answers]
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": "unknownuser",
                "questions": questions,
                "answers": answers,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Username not found")

    def test_generate_qa_verification_token_validation_failure(self):
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": "testuser1",
                "questions": [1, 2],
                "answers": ["Fluffy", "Smith"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid request")
        self.assertIn("error_content", response.json())

    def test_generate_qa_verification_token_question_not_exist(self):
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": "testuser1",
                "questions": [1, 2, 9999],
                "answers": ["Fluffy", "Smith", "Andrew"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid request")
        self.assertIn("error_content", response.json())
        self.assertEqual(
            response.json()["error_content"]["questions"][0],
            "User security questions doesn't existed",
        )

    @mock.patch("users.views.auth_views.ScopeToken.for_user")
    def test_generate_qa_verification_token_internal_server_error(
        self, mock_create_jwt
    ):
        mock_create_jwt.side_effect = Exception("JWT creation failed")
        questions_answers = UserQuestionAnswer.objects.all()
        questions = [qa.question.id for qa in questions_answers]
        answers = [qa.answer for qa in questions_answers]
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": "testuser1",
                "questions": questions,
                "answers": answers,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())

    def test_generate_password_verification_token_success(self):
        response = self.client.post(
            self.generate_password_token_url,
            {"username": "testuser1", "password": "cORRectPassw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Token generated successfully")
        scope_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]
        )
        self.assertIsNotNone(
            scope_token_cookie,
            f"The {settings.COOKIE_SETTINGS['AUTH_COOKIE_SCOPE']} cookie was not set in the response.",
        )

    def test_generate_password_verification_token_first_time_user_not_allowed(self):
        response = self.client.post(
            self.generate_password_token_url,
            {"username": "testuser", "password": "correctpassword"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(
            response.json()["message"], "User testuser hasn't setup account"
        )

    def test_generate_password_verification_token_wrong_password_failure(self):
        response = self.client.post(
            self.generate_password_token_url,
            {"username": "testuser1", "password": "wrongpassword"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid username or password")

    def test_generate_password_verification_token_validation_failure(self):
        response = self.client.post(
            self.generate_password_token_url,
            {"username": "testuser1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid request")
        self.assertIn("error_content", response.json())

    @mock.patch("users.views.auth_views.ScopeToken.for_user")
    def test_generate_password_verification_token_internal_server_error(
        self, mock_create_jwt
    ):
        mock_create_jwt.side_effect = Exception("JWT creation failed")
        response = self.client.post(
            self.generate_password_token_url,
            {"username": "testuser1", "password": "cORRectPassw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())

    def test_verify_token_success(self):
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=TokenScope.PASSWORD_VERIFY_SCOPE,
            )
        )
        response = self.client.post(
            self.verify_token_url,
            {"token_type": "scope"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Token is valid")

    def test_verify_token_validation_failure(self):
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.valid_token(
                token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
                scope=TokenScope.PASSWORD_VERIFY_SCOPE,
            )
        )
        response = self.client.post(self.verify_token_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid request")
        self.assertIn("error_content", response.json())

    def test_verify_token_token_not_found(self):
        response = self.client.post(
            self.verify_token_url, {"token_type": "scope"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertTrue("Token not found in cookie" in response.json()["message"])

    def test_verify_token_token_invalid(self):
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = (
            TokenFactory.invalid_signature()
        )
        response = self.client.post(
            self.verify_token_url, {"token_type": "scope"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid token")
        self.assertIn("error_content", response.json())

    @mock.patch("users.views.auth_views.get_token_from_cookie")
    def test_verify_token_exception(self, mock_get_token):
        mock_get_token.side_effect = Exception("Unexpected error")
        response = self.client.post(
            self.verify_token_url, {"token_type": "scope"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())

    def test_refresh_token_success(self):
        refresh_token = TokenFactory.valid_token(
            token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]
        )
        jti = get_jti_from_jwt(refresh_token)
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]] = (
            refresh_token
        )
        response = self.client.post(self.refresh_token_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Refresh token successful")
        # New access token generated
        access_token_cookie = response.cookies.get(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]
        )
        self.assertIsNotNone(
            access_token_cookie,
            f"The {settings.COOKIE_SETTINGS['AUTH_COOKIE_ACCESS']} cookie was not set in the response.",
        )
        # New refresh token generated
        new_jti = get_jti_from_jwt(
            response.cookies.get(settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]).value
        )
        self.assertNotEqual(jti, new_jti)
        # Old refresh token in blacklist
        self.assertTrue(RefreshTokenRedis.exists(jti))

    def test_refresh_token_token_not_found(self):
        response = self.client.post(self.refresh_token_url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertTrue("Token not found in cookie" in response.json()["message"])

    def test_refresh_token_token_invalid(self):
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]] = (
            TokenFactory.invalid_signature()
        )
        response = self.client.post(self.refresh_token_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid token")
        self.assertIn("error_content", response.json())

    @mock.patch("users.views.auth_views.get_token_from_cookie")
    def test_refresh_token_exception(self, mock_get_token):
        mock_get_token.side_effect = Exception("Unexpected error")
        response = self.client.post(self.refresh_token_url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())

    def test_delete_scope_token_success(self):
        scope_token = TokenFactory.valid_token(
            token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
            scope=TokenScope.PASSWORD_VERIFY_SCOPE,
        )
        jti = get_jti_from_jwt(scope_token)
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]] = scope_token
        response = self.client.post(self.delete_scope_token_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(
            response.json()["message"], "Scope tokens deleted successfully"
        )
        # Delete scope token in cookie
        # (Behind the scence: create new cookie but expired: Set-Cookie: scope=""; Max-Age=0; Path=/;)
        cookie = response.cookies.get(settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"])
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, "")
        self.assertEqual(cookie["max-age"], 0)
        # Old scope token in blacklist
        self.assertTrue(ScopeTokenRedis.exists(jti))

    def test_delete_scope_token_token_not_found(self):
        response = self.client.post(
            self.delete_scope_token_url, {BYPASS_TOKEN_NOTFOUND: False}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertTrue("Token not found in cookie" in response.json()["message"])

    @mock.patch("users.views.auth_views.get_token_from_cookie")
    def test_delete_scope_token_exception(self, mock_get_token):
        mock_get_token.side_effect = Exception("Unexpected error")
        response = self.client.post(self.delete_scope_token_url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())

    def test_logout_success(self):
        refresh_token = TokenFactory.valid_token(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]
        )
        access_token = TokenFactory.valid_token(
            settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]
        )
        jti = get_jti_from_jwt(refresh_token)
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]] = (
            refresh_token
        )
        self.client.cookies[settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]] = (
            access_token
        )
        response = self.client.post(self.logout_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Logout successfully")
        # Delete access and refresh token in cookie
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
        # Old refresh token in blacklist
        self.assertTrue(RefreshTokenRedis.exists(jti))

    def test_logout_token_not_found(self):
        response = self.client.post(
            self.logout_url, {BYPASS_TOKEN_NOTFOUND: False}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertTrue("Token not found in cookie" in response.json()["message"])

    @mock.patch("users.views.auth_views.get_token_from_cookie")
    def test_logout_exception(self, mock_get_token):
        mock_get_token.side_effect = Exception("Unexpected error")
        response = self.client.post(self.logout_url)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())
