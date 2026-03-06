from unittest import mock
from botocore.exceptions import ClientError
from django.urls import reverse
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser
from core.auth.constants import ACCESS_TOKEN
from core.storage import AvatarsMediaStorage
from core.constants import EventType, ErrorTypes
from tests.helpers.setup_mock_accounts import create_test_users, ACTIVE_USER_USERNAME
from tests.helpers.setup_mock_token import TokenFactory
from tests.helpers.utils import S3TestCase, get_error_key_response


class AvatarViewsTestCase(S3TestCase):
    bucket_name = settings.GARAGE_BUCKET_PUBLIC

    def setUp(self):
        super().setUp()
        # Generate user data
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

    def _make_image_file(
        self, filename="test_avatar.jpg", content=b"fake-image-content"
    ):
        return SimpleUploadedFile(filename, content, content_type="image/jpeg")

    def _set_avatar(self, filename="test_avatar.jpg", content=b"fake-image-content"):
        # saves to both S3 and DB
        self.user.avatar.save(filename, ContentFile(content), save=True)
        self.user.refresh_from_db()
        key = f"{AvatarsMediaStorage.location}/{self.user.avatar.name}"
        return key

    def test_upload_avatar_success(self):
        # Act
        file = self._make_image_file()
        response = self.client.patch(
            self.upload_avatar_url,
            {"image": file},
            format="multipart",
        )
        # Assert response status + structure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        # Assert response body
        self.assertEqual(response.json()["message"], "Successfully upload avatar")
        # Assert avatar actually saved in DB
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.avatar)
        self.assertIn("test_avatar", self.user.avatar.name)
        # Assert file actually exists in mock S3
        key = f"{AvatarsMediaStorage.location}/{self.user.avatar.name}"
        s3_object = self.s3.get_object(Bucket=self.bucket_name, Key=key)
        self.assertEqual(s3_object["Body"].read(), b"fake-image-content")
        # Assert url
        avatar_url = response.json()["data"]
        # Assert it's a non-empty string
        self.assertIsInstance(avatar_url, str)
        self.assertTrue(len(avatar_url) > 0)
        # Assert it contains the correct bucket and file path
        self.assertIn(self.bucket_name, avatar_url)
        self.assertIn(key, avatar_url)

    def test_upload_avatar_replaces_old_avatar(self):
        # Arrange — give user an existing avatar
        old_key = self._set_avatar("old_avatar.jpg", b"old-content")
        # Assert before Act, check if image is existed in s3
        s3_object = self.s3.get_object(Bucket=self.bucket_name, Key=old_key)
        self.assertEqual(s3_object["Body"].read(), b"old-content")
        # Act — upload new avatar
        new_file = self._make_image_file("new_avatar.jpg", b"new-content")
        self.client.patch(
            self.upload_avatar_url,
            {"image": new_file},
            format="multipart",
        )
        # Assert old file deleted from mock S3
        with self.assertRaises(ClientError):
            self.s3.get_object(Bucket=self.bucket_name, Key=old_key)
        # Assert new file exists in DB and S3
        self.user.refresh_from_db()
        self.assertIn("new_avatar", self.user.avatar.name)
        new_key = f"{AvatarsMediaStorage.location}/{self.user.avatar.name}"
        s3_object = self.s3.get_object(Bucket=self.bucket_name, Key=new_key)
        self.assertEqual(s3_object["Body"].read(), b"new-content")

    def test_upload_avatar_validation_failure(self):
        response = self.client.patch(self.upload_avatar_url, {}, format="multipart")
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "validation")
        error_item_keys = get_error_key_response(response)
        self.assertIn("avatar", error_item_keys)

    @mock.patch("users.views.avatar_views.logger")
    @mock.patch("users.views.avatar_views.JsonResponse")
    def test_upload_avatar_exception(self, mock_json_response, mock_logger):
        # Arrange: Mock fail function and set cookie
        client = APIClient(raise_request_exception=False)
        client.cookies[ACCESS_TOKEN] = TokenFactory.valid_token(
            token_type=ACCESS_TOKEN, username=ACTIVE_USER_USERNAME
        )
        exception_message = (
            "Upload avatar: Unexpected error when creating json response"
        )
        mock_json_response.side_effect = Exception(exception_message)
        # Act
        file = self._make_image_file()
        response = client.patch(
            self.upload_avatar_url,
            {"image": file},
            format="multipart",
        )
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.UPLOAD_AVATAR)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_delete_avatar_success_case_no_avatar(self):
        # Act — upload new avatar
        response = self.client.delete(self.delete_avatar_url)
        # Assert response status
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_avatar_success_case_exist_avatar(self):
        # Arrange — give user an existing avatar
        key = self._set_avatar()
        # Act — upload new avatar
        self.client.delete(self.delete_avatar_url)
        # Assert file deleted from mock S3 and DB
        with self.assertRaises(ClientError):
            self.s3.get_object(Bucket=self.bucket_name, Key=key)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    @mock.patch("users.views.avatar_views.logger")
    @mock.patch("users.views.avatar_views.JsonResponse")
    def test_delete_avatar_exception(self, mock_json_response, mock_logger):
        # Arrange: Mock fail function and set cookie
        client = APIClient(raise_request_exception=False)
        client.cookies[ACCESS_TOKEN] = TokenFactory.valid_token(
            token_type=ACCESS_TOKEN, username=ACTIVE_USER_USERNAME
        )
        exception_message = (
            "Delete avatar: Unexpected error when creating json response"
        )
        mock_json_response.side_effect = Exception(exception_message)
        # Act
        response = client.delete(self.delete_avatar_url)
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.DELETE_AVATAR)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")

    def test_get_avatar_success_case_no_avatar(self):
        # Act — upload new avatar
        response = self.client.get(self.get_avatar_url)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertResponseStructure(response, has_data=True)
        self.assertIsNone(response.json()["data"])

    def test_get_avatar_success_case_exist_avatar(self):
        # Arrange — give user an existing avatar
        key = self._set_avatar()
        # Act — upload new avatar
        response = self.client.get(self.get_avatar_url)
        # Assert correct url return
        avatar_url = response.json()["data"]
        # Assert it's a non-empty string
        self.assertIsInstance(avatar_url, str)
        self.assertTrue(len(avatar_url) > 0)
        # Assert it contains the correct bucket and file path
        self.assertIn(self.bucket_name, avatar_url)
        self.assertIn(key, avatar_url)

    @mock.patch("users.views.avatar_views.logger")
    @mock.patch("users.views.avatar_views.JsonResponse")
    def test_get_avatar_exception(self, mock_json_response, mock_logger):
        # Arrange: Mock fail function and set cookie
        client = APIClient(raise_request_exception=False)
        client.cookies[ACCESS_TOKEN] = TokenFactory.valid_token(
            token_type=ACCESS_TOKEN, username=ACTIVE_USER_USERNAME
        )
        exception_message = "Get avatar: Unexpected error when creating json response"
        mock_json_response.side_effect = Exception(exception_message)
        # Act
        response = client.get(self.get_avatar_url)
        # Assert log content to log correct exception
        mock_logger.error.assert_called_once()
        logged_data = mock_logger.error.call_args[0][0]
        self.assertEqual(logged_data["event_type"], EventType.GET_AVATAR)
        self.assertEqual(logged_data["error_type"], ErrorTypes.EXCEPTION)
        self.assertEqual(logged_data["error_content"], exception_message)
        # Assert response
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertResponseStructure(response)
        self.assertEqual(response.json()["code"], "error")
