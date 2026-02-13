from unittest import mock
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.helpers.setup_mock_accounts import create_security_questions
from tests.helpers.utils import get_error_key_response, CustomAPITestCase
from core.constants import ErrorTypes, EventType


class SecurityQuestionsViewsTestCase(CustomAPITestCase):
    def setUp(self):
        self.client = APIClient()
        self.get_security_questions_url = reverse("security_question-list")
        create_security_questions()

    def test_get_all_security_questions_success(self):
        # Act
        response = self.client.get(self.get_security_questions_url)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        self.assertEqual(
            response.json()["message"], "Successfully retrieve security questions"
        )
        self.assertEqual(len(response.json()["data"]), 8)

    def test_filter_security_questions_success(self):
        # Act
        response = self.client.get(
            self.get_security_questions_url, {"status": "Official"}
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        self.assertEqual(
            response.json()["message"], "Successfully retrieve security questions"
        )
        self.assertEqual(len(response.json()["data"]), 6)
        # Assert filter ok
        for question in response.json()["data"]:
            self.assertEqual(question["status"], "Official")

    def test_get_security_questions_validation_failure(self):
        # Act
        response = self.client.get(
            self.get_security_questions_url, {"status": "Unknown"}
        )
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "validation")
        error_item_keys = get_error_key_response(response)
        self.assertIn("status", error_item_keys)

    @mock.patch("users.views.security_question_views.logger")
    @mock.patch(
        "users.views.security_question_views.SecurityQuestionSearchParam.is_valid"
    )
    def test_get_security_questions_internal_server_error(
        self, mock_validate, mock_logger
    ):
        # Arrange: mock fail function
        client = APIClient(raise_request_exception=False)
        exception_message = (
            "Get security questions: Unexpected error when validate query params"
        )
        mock_validate.side_effect = Exception(exception_message)
        # Act
        response = client.get(self.get_security_questions_url)
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.LIST_SECURITY_QUESTIONS)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")
