from django.test import TestCase

from users.serializers import (
    SetSecurityQASerializer,
    GetSecurityQAVerificationTokenSerializer,
)
from tests.helpers.setup_mock_accounts import create_security_questions


class SetSecurityQASerializerTest(TestCase):
    def setUp(self):
        security_question_instances = create_security_questions()
        self.official_questions = security_question_instances.filter(
            status="Official"
        ).order_by("id")
        self.unofficial_question = security_question_instances.filter(
            status="Unofficial"
        ).first()

    def test_validate_questions_success(self):
        data = {
            "token": "sometoken",
            "questions": [q.id for q in self.official_questions],
            "answers": ["a", "b", "c"],
        }

        serializer = SetSecurityQASerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        validated_questions = serializer.validated_data["questions"]
        self.assertEqual(
            [q.id for q in validated_questions],
            [q.id for q in self.official_questions],
        )

    def test_validate_questions_with_duplicates(self):
        data = {
            "token": "sometoken",
            "questions": [q.id for q in self.official_questions[:2]]
            + [self.official_questions[0].id],
            "answers": ["a", "b", "c"],
        }

        serializer = SetSecurityQASerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("questions", serializer.errors)
        self.assertIn(
            "Number of Questions must equals to", serializer.errors["questions"][0]
        )

    def test_validate_questions_with_nonexistent_id(self):
        non_existent_id = 9999
        data = {
            "token": "sometoken",
            "questions": [q.id for q in self.official_questions[:2]]
            + [non_existent_id],
            "answers": ["a", "b", "c"],
        }

        serializer = SetSecurityQASerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("questions", serializer.errors)
        self.assertEqual(serializer.errors["questions"][0], "Non-exist questions")

    def test_validate_questions_with_non_official_question(self):
        data = {
            "token": "sometoken",
            "questions": [q.id for q in self.official_questions[:2]]
            + [self.unofficial_question.id],
            "answers": ["a", "b", "c"],
        }

        serializer = SetSecurityQASerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("questions", serializer.errors)
        self.assertEqual(serializer.errors["questions"][0], "Non-exist questions")


class GetSecurityQAVerificationTokenSerializerTest(TestCase):
    def test_validate_questions_success(self):
        data = {
            "username": "testuser",
            "questions": [1, 2, 3],
            "answers": ["a", "b", "c"],
        }

        serializer = GetSecurityQAVerificationTokenSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_validate_questions_number_of_questions_not_equal_to_number_of_answer(self):
        data = {
            "username": "testuser",
            "questions": [1, 1, 2],
            "answers": ["a", "b", "c"],
        }

        serializer = GetSecurityQAVerificationTokenSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("questions", serializer.errors)
        self.assertIn(
            "Number of Questions must equals to", serializer.errors["questions"][0]
        )
