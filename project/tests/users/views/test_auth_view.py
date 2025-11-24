from unittest import mock
from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from users.models import UserQuestionAnswer
from tests.helpers.setup_mock_accounts import setup_mock_accounts


class AuthViewsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.login_url = reverse("auth-login")
        self.generate_qa_token_url = reverse(
            "auth-generate-question-answer-verification-token"
        )
        self.generate_password_token_url = reverse(
            "auth-generate-password-verification-token"
        )
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
            {
                "username": "testuser",
            },
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
            {
                "username": "testuser1",
            },
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
