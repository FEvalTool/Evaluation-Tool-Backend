import json
from django.test import TestCase

from temps.models import Student


class ModelsTestCase(TestCase):
    def test_student_str(self):
        student = Student(
            first_name="Alice",
            last_name="Brown",
            email="alice.brown@example.com",
        )
        expected_result = f"{student.first_name} {student.last_name}"

        self.assertEqual(expected_result, student.__str__())
