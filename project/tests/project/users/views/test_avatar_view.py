from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from users.models import CustomUser
from tests.helpers.setup_mock_accounts import create_test_users, ACTIVE_USER_USERNAME
from tests.helpers.setup_mock_token import TokenFactory
from tests.helpers.utils import S3TestCase
from core.auth.constants import ACCESS_TOKEN


class AvatarViewsTestCase(S3TestCase):
    def setUp(self):
        super().setUp()
        create_test_users()
        self.user = CustomUser.objects.get(username=ACTIVE_USER_USERNAME)
        # Set up API client
        self.client = APIClient()
        self.client.cookies[ACCESS_TOKEN] = TokenFactory.valid_token(
            token_type=ACCESS_TOKEN,
            username=ACTIVE_USER_USERNAME,
        )

        # Set up urls
        self.upload_avatar_url = reverse("avatar-upload")
        self.delete_avatar_url = reverse("avatar-delete")
        self.get_avatar_url = reverse("avatar-get")

    def _make_image_file(self, filename="test_avatar.jpg"):
        return SimpleUploadedFile(
            filename,
            b"fake-image-content",
            content_type="image/jpeg",
        )

    def test_upload_avatar_success(self):
        file = self._make_image_file()

        response = self.client.patch(
            self.upload_avatar_url,
            {"image": file},
            format="multipart",
        )

        # Assert response
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.json())

        # Assert avatar actually saved in DB
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.avatar)
        self.assertIn("test_avatar", self.user.avatar.name)

        # # Assert file actually exists in mock S3
        s3_object = self.s3.get_object(
            Bucket="test-bucket",
            Key=f"media/avatars/{self.user.avatar.name}",
        )
        self.assertEqual(s3_object["Body"].read(), b"fake-image-content")

    def test_upload_avatar_replaces_old_avatar(self):
        # Arrange — give user an existing avatar
        old_file = SimpleUploadedFile(
            "old_avatar.jpg", b"old-content", content_type="image/jpeg"
        )
        response = self.client.patch(
            self.upload_avatar_url,
            {"image": old_file},
            format="multipart",
        )
        self.user.refresh_from_db()
        old_key = self.user.avatar.name

        # Act — upload new avatar
        new_file = SimpleUploadedFile(
            "new_avatar.jpg", b"new-content", content_type="image/jpeg"
        )
        response = self.client.patch(
            self.upload_avatar_url,
            {"image": new_file},
            format="multipart",
        )

        # Assert old file deleted from mock S3
        from botocore.exceptions import ClientError

        with self.assertRaises(ClientError):
            self.s3.get_object(Bucket="test-bucket", Key=old_key)

        # Assert new file exists in DB and S3
        self.user.refresh_from_db()
        self.assertIn("new_avatar", self.user.avatar.name)

    def test_upload_avatar_validation_failure(self):
        response = self.client.patch(self.upload_avatar_url, {}, format="multipart")
        self.assertEqual(response.status_code, 400)
