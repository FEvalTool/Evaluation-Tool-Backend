import boto3
from moto import mock_aws
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from users.models import CustomUser
from users.views.avatar_views import AvatarViewSet
from tests.helpers.setup_mock_accounts import create_test_users, ACTIVE_USER_USERNAME
from tests.helpers.setup_mock_token import TokenFactory
from core.auth.constants import ACCESS_TOKEN


MOTO_SETTINGS = {
    "AWS_ACCESS_KEY_ID": "fake-key",
    "AWS_SECRET_ACCESS_KEY": "fake-secret",
    "AWS_STORAGE_BUCKET_NAME": "test-bucket",
    "AWS_S3_REGION_NAME": "us-east-1",
    "AWS_S3_ENDPOINT_URL": None,  # must be None so moto can intercept
    "AWS_S3_SIGNATURE_VERSION": "s3v4",
}


@mock_aws
@override_settings(**MOTO_SETTINGS)
class AvatarViewsTestCase(TestCase):
    def setUp(self):
        # Create mock bucket
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket="test-bucket")

        # Reinitialize field storage inside moto context
        from users.models import CustomUser
        from core.storage import AvatarsMediaStorage

        CustomUser.avatar.field.storage = AvatarsMediaStorage()

        # Create user
        create_test_users()
        self.user = CustomUser.objects.get(username=ACTIVE_USER_USERNAME)

        self.avatar_store_location = AvatarsMediaStorage().location

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

        # Assert file actually exists in mock S3
        s3_object = self.s3.get_object(
            Bucket="test-bucket",
            Key=f"{self.avatar_store_location}/{self.user.avatar.name}",
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
