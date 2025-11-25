from django.test import TestCase

from users.models import CustomUser
from users.utils import generate_username


class UtilsTestCase(TestCase):
    def test_generate_username_unique(self):
        CustomUser.objects.create(
            username="VuTA1",
            name="Trinh Anh Vu",
            phone_number="0987654321",
            dob="2000-01-01",
            identity_number="123456789999",
        )
        username = generate_username("Tran Anh Vu")
        self.assertEqual(username, "VuTA2")

    def test_generate_username_with_extra_spaces(self):
        username = generate_username("  Tran   Anh   Vu  ")
        # No user exists yet, expect VuTA1
        self.assertEqual(username, "VuTA1")

    def test_generate_username_different_name(self):
        username = generate_username("Nguyen Van An")
        self.assertEqual(username, "AnNV1")
