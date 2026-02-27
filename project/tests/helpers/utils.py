import boto3
from moto import mock_aws
from django.test import TestCase, override_settings


def get_error_key_response(response):
    """Retrieving error key list from validation error response"""
    error_item_keys = set()
    if "error" in response.json():
        for error in response.json()["error"]:
            error_item_keys.add(error["field"])
    return error_item_keys


class CustomAPITestCase(TestCase):
    def assertResponseStructure(self, response, has_data=False):
        """
        Validates response structure based on status code.
        - 2xx: checks success response structure
        - 4xx/5xx: checks error response structure

        If has_data == True, check if response has 'data' field
        """
        data = response.json()
        status_code = response.status_code

        # Check success response (2xx)
        if 200 <= status_code < 300:
            self.assertIn(
                "message",
                data,
                f"Success response missing 'message' field (status: {status_code})",
            )
            if has_data:
                self.assertIn(
                    "data",
                    data,
                    f"Success response missing 'data' field (status: {status_code})",
                )

        # Check error response (4xx, 5xx)
        elif 400 <= status_code < 600:
            self.assertIn(
                "message",
                data,
                f"Error response missing 'message' field (status: {status_code})",
            )
            # 'error' is only appear in 400 validation error response
            if status_code == 400:
                self.assertIn(
                    "error",
                    data,
                    f"Error response missing 'error' field (status: {status_code})",
                )

        else:
            self.fail(f"Unexpected status code: {status_code}")

        return data


MOTO_SETTINGS = {
    "AWS_ACCESS_KEY_ID": "fake-key",
    "AWS_SECRET_ACCESS_KEY": "fake-secret",
    "AWS_STORAGE_BUCKET_NAME": "test-bucket",
    "AWS_S3_REGION_NAME": "us-east-1",
    "AWS_S3_ENDPOINT_URL": None,
    "AWS_S3_SIGNATURE_VERSION": "s3v4",
}


@override_settings(**MOTO_SETTINGS)
class S3TestCase(CustomAPITestCase):
    """
    Base test class for any test that involves S3 storage.
    Inherits CustomAPITestCase so S3 tests also have access
    to assertResponseStructure and other helpers.
    """

    bucket_name = "test-bucket"

    def setUp(self):
        # Start moto explicitly before anything else
        self.mock_aws = mock_aws()
        self.mock_aws.start()

        # Create mock bucket
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket=self.bucket_name)

        # Reinitialize field storage inside active moto context
        from users.models import CustomUser
        from core.storage.avatar import AvatarsMediaStorage

        CustomUser.avatar.field.storage = AvatarsMediaStorage()

    def tearDown(self):
        # Stop moto after each test
        self.mock_aws.stop()

        # Restore original storage instances
        from core.storage.avatar import AvatarsMediaStorage
        from users.models import CustomUser

        CustomUser.avatar.field.storage = AvatarsMediaStorage()
