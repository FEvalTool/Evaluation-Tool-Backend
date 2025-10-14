from unittest import mock
from django.urls import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser, SecurityQuestion, UserQuestionAnswer
from users.utils import create_jwt
from users.constants import TokenScope


class AccountViewsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
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

        first_time_setup_user = CustomUser(**user_info_list[0])
        first_time_setup_user.set_password("correctpassword")
        normal_user = CustomUser(**user_info_list[1])
        normal_user.set_password("cORRectPassw0rd!")
        first_time_setup_user.save()
        normal_user.save()

        question_list = [
            {"content": "What is your mother's maiden name?", "status": "Official"},
            {"content": "What is your pet's name?", "status": "Official"},
            {
                "content": "What was the name of your first school?",
                "status": "Official",
            },
        ]
        SecurityQuestion.objects.bulk_create(
            [SecurityQuestion(**data) for data in question_list]
        )
        question_instances = SecurityQuestion.objects.all().order_by("content")

        answer_list = [
            {
                "user": normal_user,
                "question": question_instances[0],
                "answer": "Smith",
            },
            {
                "user": normal_user,
                "question": question_instances[1],
                "answer": "Fluffy",
            },
            {
                "user": normal_user,
                "question": question_instances[2],
                "answer": "Greenwood",
            },
        ]
        UserQuestionAnswer.objects.bulk_create(
            [UserQuestionAnswer(**data) for data in answer_list]
        )

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

    @mock.patch("users.views.generate_username")
    def test_create_account_internal_server_error(self, mock_generate_username):
        mock_generate_username.side_effect = Exception("Unexpected error")

        response = self.client.post(self.account_url, self.user_info)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())

    def test_set_password_success(self):
        token = create_jwt(
            {"username": "testuser1", "scope": TokenScope.PASSWORD_VERIFY_SCOPE}
        )
        response = self.client.post(
            self.set_password_url, {"token": token, "password": "NewPassword123!"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Successfully set new password")

    def test_set_password_validation_failure(self):
        response = self.client.post(
            self.set_password_url, {"password": "NewPassword123!"}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid request")
        self.assertIn("error_content", response.json())

    def test_set_password_invalid_token(self):
        response = self.client.post(
            self.set_password_url,
            {"token": "invalid.token.here", "password": "NewPassword123!"},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid token")
        self.assertIn("error_content", response.json())

    def test_set_password_username_not_exist(self):
        token = create_jwt(
            {"username": "unknownuser", "scope": TokenScope.PASSWORD_VERIFY_SCOPE}
        )
        response = self.client.post(
            self.set_password_url, {"token": token, "password": "NewPassword123!"}
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("message", response.json())
        self.assertEqual(
            response.json()["message"], "User with username unknownuser is not existed"
        )

    @mock.patch("users.views.decode_and_verify_jwt")
    def test_set_password_internal_server_error(self, mock_decode_and_verify_jwt):
        mock_decode_and_verify_jwt.side_effect = Exception("Unexpected error")
        token = create_jwt(
            {"username": "testuser1", "scope": TokenScope.PASSWORD_VERIFY_SCOPE}
        )
        response = self.client.post(
            self.set_password_url, {"token": token, "password": "NewPassword123!"}
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

    @mock.patch("users.views.CustomUser.objects.get")
    def test_get_user_security_questions_internal_server_error(self, mock_get_user):
        mock_get_user.side_effect = Exception("Unexpected error")
        response = self.client.get(
            self.get_user_security_questions_url, {"username": "testuser1"}
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())
