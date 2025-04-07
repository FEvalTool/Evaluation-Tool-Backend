import json
from django.urls import reverse
from rest_framework.test import APITestCase

from temps.models import Student


class StudentViewsTestCase(APITestCase):
    def setUp(self):
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
        # Disabled auto_now_add in created date
        Student.created_date.field.auto_now_add = False
        Student.objects.bulk_create(data_instances)

    def test_get_all_students(self):
        url = reverse("student")
        response = self.client.get(url, {"all": True})
        expected_result = [
            {
                "id": item["id"],
                "first_name": item["first_name"],
                "last_name": item["last_name"],
                "created_date": item["created_date"]
            }
            for item in self.students_data
        ]

        returned_result = json.loads(response.content)['result']

        self.assertEqual(len(returned_result), len(expected_result))
        self.assertEqual(returned_result[0], expected_result[0])

