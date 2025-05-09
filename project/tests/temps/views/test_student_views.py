from datetime import datetime
from unittest import mock
from django.urls import reverse
from rest_framework.test import APITestCase

from temps.models import Student
from temps.constants import (
    DEFAULT_PAGE_SIZE,
    INTERNAL_SERVER_ERROR,
    VALIDATION_ERROR,
    DOES_NOT_EXIST_ERROR,
)


class StudentViewsTestCase(APITestCase):
    def setUp(self):
        self.url = reverse("student")

        self.students_data = [
            {
                "id": 1,
                "first_name": "Alice",
                "last_name": "Brown",
                "email": "alice.brown@example.com",
                "created_date": "2025-04-01T08:00:00Z",
                "updated_at": "2025-04-01T08:00:00Z",
            },
            {
                "id": 2,
                "first_name": "Bob",
                "last_name": "Smith",
                "email": "bob.smith@example.com",
                "created_date": "2025-04-01T10:00:00Z",
                "updated_at": "2025-04-01T10:00:00Z",
            },
            {
                "id": 3,
                "first_name": "Alice",
                "last_name": "Anderson",
                "email": "alice.anderson@example.com",
                "created_date": "2025-04-01T09:00:00Z",
                "updated_at": "2025-04-01T09:00:00Z",
            },
            {
                "id": 4,
                "first_name": "Charlie",
                "last_name": "Davis",
                "email": "charlie.davis@example.com",
                "created_date": "2025-04-01T07:00:00Z",
                "updated_at": "2025-04-01T07:00:00Z",
            },
            {
                "id": 5,
                "first_name": "David",
                "last_name": "Evans",
                "email": "david.evans@example.com",
                "created_date": "2025-04-01T12:00:00Z",
                "updated_at": "2025-04-01T12:00:00Z",
            },
            {
                "id": 6,
                "first_name": "Bob",
                "last_name": "Adams",
                "email": "bob.adams@example.com",
                "created_date": "2025-04-01T11:00:00Z",
                "updated_at": "2025-04-01T11:00:00Z",
            },
        ]
        data_instances = [Student(**data) for data in self.students_data]
        # Temporary disabled auto date in "created_date" and "updated_at" fields when create test data
        Student.created_date.field.auto_now_add = False
        Student.updated_at.field.auto_now = False
        Student.objects.bulk_create(data_instances)
        Student.created_date.field.auto_now_add = True
        Student.updated_at.field.auto_now = True

        self.created_data_payload = {"first_name": "Andrew", "last_name": "Jackson"}

    def url_with_pk(self, pk):
        url = reverse("student-detail", kwargs={"pk": pk})
        return url

    def test_get_all_students(self):
        response = self.client.get(self.url, {"all": True})
        returned_result = response.json()["result"]

        expected_result = [
            {
                "id": item["id"],
                "first_name": item["first_name"],
                "last_name": item["last_name"],
                "created_date": item["created_date"],
            }
            for item in self.students_data
        ]

        self.assertEqual(len(returned_result), len(expected_result))
        self.assertEqual(returned_result, expected_result)

    def test_get_all_students_sort_with_first_name_and_last_name(self):
        response = self.client.get(
            self.url,
            {
                "all": True,
                "sort_keys[0]": "first_name",
                "sort_orders[0]": "1",
                "sort_keys[1]": "last_name",
                "sort_orders[1]": "-1",
            },
        )
        returned_result = response.json()["result"]

        expected_result = [
            {
                "id": item["id"],
                "first_name": item["first_name"],
                "last_name": item["last_name"],
                "created_date": item["created_date"],
            }
            for item in self.students_data
        ]
        expected_result = sorted(
            expected_result, key=lambda x: (x["first_name"], -ord(x["last_name"][0]))
        )

        self.assertEqual(len(returned_result), len(expected_result))
        self.assertEqual(returned_result, expected_result)

    def test_get_students_without_filtering(self):
        response = self.client.get(self.url)
        returned_result = response.json()["result"]

        expected_result = [
            {
                "id": item["id"],
                "first_name": item["first_name"],
                "last_name": item["last_name"],
                "created_date": item["created_date"],
            }
            for item in self.students_data[:DEFAULT_PAGE_SIZE]
        ]

        self.assertEqual(len(returned_result), len(expected_result))
        self.assertEqual(returned_result, expected_result)

    def test_get_students_empty_page(self):
        last_page_index = int(len(self.students_data) / DEFAULT_PAGE_SIZE) + 1
        response = self.client.get(self.url, {"page_index": last_page_index + 3})
        returned_result = response.json()["result"]

        students_data_from_index = (
            int(len(self.students_data) / DEFAULT_PAGE_SIZE) * DEFAULT_PAGE_SIZE
        )
        expected_result = [
            {
                "id": item["id"],
                "first_name": item["first_name"],
                "last_name": item["last_name"],
                "created_date": item["created_date"],
            }
            for item in self.students_data[students_data_from_index:]
        ]

        self.assertEqual(len(returned_result), len(expected_result))
        self.assertEqual(returned_result, expected_result)

    def test_get_all_students_query_params_validation_error(self):
        # Case 1: sort_orders and sort_keys length is unequal
        response_case1 = self.client.get(
            self.url,
            {
                "all": True,
                "sort_keys[0]": "first_name",
                "sort_orders[0]": "1",
                "sort_keys[1]": "last_name",
            },
        )
        returned_result_case1 = response_case1.json()

        expected_result_case1 = {
            "message_type": VALIDATION_ERROR,
            "error-content": {
                "non_field_errors": ["Sort keys and Sort values must have same length"]
            },
        }

        self.assertEqual(response_case1.status_code, 400)
        self.assertEqual(returned_result_case1, expected_result_case1)

        # Case 2: sort_orders value is invalid
        response_case2 = self.client.get(
            self.url,
            {
                "all": True,
                "sort_keys[0]": "first_name",
                "sort_orders[0]": "5",
            },
        )
        returned_result_case2 = response_case2.json()

        expected_result_case2 = {
            "message_type": VALIDATION_ERROR,
            "error-content": {"sort_orders": ["Sort orders must be 1 or -1"]},
        }

        self.assertEqual(response_case2.status_code, 400)
        self.assertEqual(returned_result_case2, expected_result_case2)

    @mock.patch("temps.views.student_views.get_sort_query")
    def test_get_students_exception(self, mock_get_sort_query):
        mock_get_sort_query.side_effect = ValueError("Mocked error")
        response = self.client.get(self.url)
        returned_result = response.json()

        expected_result = {
            "message_type": INTERNAL_SERVER_ERROR,
            "error-content": "Mocked error",
        }

        self.assertEqual(response.status_code, 500)
        self.assertEqual(returned_result, expected_result)

    def test_create_student(self):
        response = self.client.post(self.url, data=self.created_data_payload)
        returned_result = response.json()

        self.assertEqual(returned_result["first_name"], "Andrew")
        self.assertEqual(returned_result["last_name"], "Jackson")

    def test_create_student_payload_validation_error(self):
        # Missing first_name field
        invalid_payload = self.created_data_payload.copy()
        invalid_payload.pop("first_name")
        response = self.client.post(self.url, data=invalid_payload)
        returned_result = response.json()

        expected_result = {
            "message_type": VALIDATION_ERROR,
            "error-content": {"first_name": ["This field is required."]},
        }

        self.assertEqual(response.status_code, 400)
        self.assertEqual(returned_result, expected_result)

    @mock.patch("temps.views.student_views.Student.objects.create")
    def test_create_student_exception(self, mock_create_func):
        mock_create_func.side_effect = ValueError("Mocked error")
        response = self.client.post(self.url, data=self.created_data_payload)
        returned_result = response.json()

        expected_result = {
            "message_type": INTERNAL_SERVER_ERROR,
            "error-content": "Mocked error",
        }

        self.assertEqual(response.status_code, 500)
        self.assertEqual(returned_result, expected_result)

    def test_get_student_detail(self):
        url = self.url_with_pk(1)
        response = self.client.get(url)
        returned_result = response.json()

        expected_result = self.students_data[0]

        self.assertEqual(returned_result, expected_result)

    def test_get_student_detail_not_found(self):
        url = self.url_with_pk(20)
        response = self.client.get(url)
        returned_result = response.json()

        expected_result = {
            "message_type": DOES_NOT_EXIST_ERROR,
            "error-content": "Student with id = 20 does not exist",
        }

        self.assertEqual(response.status_code, 404)
        self.assertEqual(returned_result, expected_result)

    @mock.patch("temps.views.student_views.Student.objects.get")
    def test_get_student_detail_exception(self, mock_get_func):
        mock_get_func.side_effect = ValueError("Mocked error")
        url = self.url_with_pk(1)
        response = self.client.get(url)
        returned_result = response.json()

        expected_result = {
            "message_type": INTERNAL_SERVER_ERROR,
            "error-content": "Mocked error",
        }

        self.assertEqual(response.status_code, 500)
        self.assertEqual(returned_result, expected_result)

    def test_update_student(self):
        url = self.url_with_pk(1)
        update_payload = self.students_data[0].copy()
        update_payload.pop("id")
        update_payload.pop("created_date")
        update_payload.pop("updated_at")
        update_payload["first_name"] = "Megan"
        response = self.client.put(url, data=update_payload)
        returned_result = response.json()
        new_updated_at = datetime.fromisoformat(returned_result.pop("updated_at"))

        original_updated_at = datetime.fromisoformat(
            self.students_data[0].get("updated_at")
        )
        expected_result = self.students_data[0]
        expected_result["first_name"] = "Megan"
        expected_result.pop("updated_at")

        self.assertEqual(returned_result, expected_result)
        self.assertLess(original_updated_at, new_updated_at)

    def test_update_student_not_found(self):
        url = self.url_with_pk(20)
        update_payload = self.students_data[0].copy()
        response = self.client.put(url, data=update_payload)
        returned_result = response.json()

        expected_result = {
            "message_type": DOES_NOT_EXIST_ERROR,
            "error-content": "Student with id = 20 does not exist",
        }

        self.assertEqual(response.status_code, 404)
        self.assertEqual(returned_result, expected_result)

    def test_update_student_payload_validation_error(self):
        # Missing first_name field
        url = self.url_with_pk(1)
        invalid_payload = self.students_data[0].copy()
        invalid_payload.pop("id")
        invalid_payload.pop("created_date")
        invalid_payload.pop("updated_at")
        invalid_payload.pop("first_name")
        response = self.client.put(url, data=invalid_payload)
        returned_result = response.json()

        expected_result = {
            "message_type": VALIDATION_ERROR,
            "error-content": {"first_name": ["This field is required."]},
        }

        self.assertEqual(response.status_code, 400)
        self.assertEqual(returned_result, expected_result)

    @mock.patch("temps.views.student_views.Student.objects.get")
    def test_update_student_exception(self, mock_get_func):
        mock_get_func.side_effect = ValueError("Mocked error")
        url = self.url_with_pk(1)
        update_payload = self.students_data[0].copy()
        response = self.client.put(url, data=update_payload)
        returned_result = response.json()

        expected_result = {
            "message_type": INTERNAL_SERVER_ERROR,
            "error-content": "Mocked error",
        }

        self.assertEqual(response.status_code, 500)
        self.assertEqual(returned_result, expected_result)

    def test_delete_student(self):
        url = self.url_with_pk(1)
        response = self.client.delete(url)

        checked_data_exist = Student.objects.filter(id=1)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(checked_data_exist), 0)

    def test_delete_student_detail_not_found(self):
        url = self.url_with_pk(20)
        response = self.client.delete(url)
        returned_result = response.json()

        expected_result = {
            "message_type": DOES_NOT_EXIST_ERROR,
            "error-content": "Student with id = 20 does not exist",
        }

        self.assertEqual(response.status_code, 404)
        self.assertEqual(returned_result, expected_result)

    @mock.patch("temps.views.student_views.Student.objects.get")
    def test_delete_student_detail_exception(self, mock_get_func):
        mock_get_func.side_effect = ValueError("Mocked error")
        url = self.url_with_pk(1)
        response = self.client.delete(url)
        returned_result = response.json()

        expected_result = {
            "message_type": INTERNAL_SERVER_ERROR,
            "error-content": "Mocked error",
        }

        self.assertEqual(response.status_code, 500)
        self.assertEqual(returned_result, expected_result)
