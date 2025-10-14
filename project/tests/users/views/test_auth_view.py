from unittest import mock
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser, SecurityQuestion, UserQuestionAnswer


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
        self.assertIn("error_content", response.json())
        self.assertIn("password", response.json()["error_content"])

    @mock.patch("users.views.create_jwt")
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
        self.assertIn("token", response.json())

    def test_generate_qa_verification_token_first_time_user_not_allowed(self):
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": "testuser",
                "questions": [1, 2, 3],
                "answers": ["Smith", "Fluffy", "Greenwood"],
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
        answers = ["error"] * 3
        response = self.client.post(
            self.generate_qa_token_url,
            {
                "username": "testuser1",
                "questions": questions,
                "answers": answers,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Security QA validation failed")

    def test_generate_qa_verification_username_not_found(self):
        questions_answers = UserQuestionAnswer.objects.all()
        questions = [qa.question.id for qa in questions_answers]
        answers = ["error"] * 3
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

    @mock.patch("users.views.create_jwt")
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
        self.assertIn("token", response.json())

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

    @mock.patch("users.views.create_jwt")
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
