from unittest import mock
from django.urls import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from tests.helpers.setup_mock_accounts import create_security_questions


class SecurityQuestionsViewsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.get_security_questions_url = reverse("question-list")
        create_security_questions()

    def test_get_all_security_questions_success(self):
        response = self.client.get(self.get_security_questions_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(
            response.json()["message"], "Successfully retrieve security questions"
        )
        self.assertIn("questions", response.json())
        self.assertEqual(len(response.json()["questions"]), 4)

    def test_filter_security_questions_success(self):
        response = self.client.get(
            self.get_security_questions_url, {"status": "Official"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.json())
        self.assertEqual(
            response.json()["message"], "Successfully retrieve security questions"
        )
        self.assertIn("questions", response.json())
        self.assertEqual(len(response.json()["questions"]), 3)
        for question in response.json()["questions"]:
            self.assertEqual(question["status"], "Official")

    def test_get_security_questions_validation_failure(self):
        response = self.client.get(
            self.get_security_questions_url, {"status": "Unknown"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Invalid request")

    @mock.patch("users.views.question_views.SecurityQuestionQuerySerializer.is_valid")
    def test_get_security_questions_internal_server_error(self, mock_validate):
        mock_validate.side_effect = Exception("Unexpected error")
        response = self.client.get(self.get_security_questions_url)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("message", response.json())
        self.assertEqual(response.json()["message"], "Internal server error")
        self.assertIn("error_content", response.json())
