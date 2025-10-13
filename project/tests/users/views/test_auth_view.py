from unittest import mock
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser


class AuthViewsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.login_url = reverse("auth-login")
        user_info_list = [
            {
                "username": "testuser",
                "name": "Test User",
                "phone_number": "0123456789",
                "dob": "1990-01-01",
                "identity_number": "123456789012",
            },
            {
                "username": "testuser1",
                "name": "Test User 1",
                "phone_number": "0987654321",
                "dob": "2000-01-01",
                "identity_number": "123456789999",
                "is_default_password": False,
                "is_security_question_set": True,
            },
        ]
        self.first_time_setup_user = CustomUser(**user_info_list[0])
        self.first_time_setup_user.set_password("correctpassword")
        self.normal_user = CustomUser(**user_info_list[1])
        self.normal_user.set_password("cORRectPassw0rd!")

        self.first_time_setup_user.save()
        self.normal_user.save()

    def test_login_success_first_time_setup_user(self):
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "correctpassword"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["is_default_password"], True)
        self.assertEqual(response.json()["is_security_question_set"], False)
        self.assertIn("tokens", response.json())
        self.assertIn("access", response.json()["tokens"])
        self.assertIn("password_verification", response.json()["tokens"])

    def test_login_success_normal_user(self):
        response = self.client.post(
            self.login_url,
            {"username": "testuser1", "password": "cORRectPassw0rd!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["is_default_password"], False)
        self.assertEqual(response.json()["is_security_question_set"], True)
        self.assertIn("tokens", response.json())
        self.assertIn("access", response.json()["tokens"])
        self.assertNotIn("password_verification", response.json()["tokens"])

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
        self.assertIn("error-content", response.json())
        self.assertIn("password", response.json()["error-content"])

    @mock.patch("users.views.create_jwt")
    def test_login_internal_server_error(self, mock_create_jwt):
        response = self.client.post(
            self.login_url,
            {"username": "testuser", "password": "correctpassword"},
            content_type="application/json",
        )
        mock_create_jwt.side_effect = Exception("JWT creation failed")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
