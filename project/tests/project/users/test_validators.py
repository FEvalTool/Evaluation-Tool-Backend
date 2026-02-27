from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import serializers
from users.validators import UserValidators, AvatarImgValidators


class UserValidatorsTestCase(TestCase):
    def test_validate_valid_password(self):
        UserValidators.password_validator("Password12345@")

    def test_validate_invalid_password(self):
        with self.assertRaises(serializers.ValidationError) as ctx:
            UserValidators.password_validator("password")
        self.assertIn("password", ctx.exception.detail)


class AvatarImgValidatorsTestCase(TestCase):
    def _make_file(
        self, filename="test.jpg", content=b"content", content_type="image/jpeg"
    ):
        return SimpleUploadedFile(filename, content, content_type=content_type)

    def test_validate_none_file(self):
        with self.assertRaises(serializers.ValidationError) as ctx:
            AvatarImgValidators.validate(None)
        self.assertIn("avatar", ctx.exception.detail)

    def test_validate_valid_content_type(self):
        for ct in ["image/jpeg", "image/png", "image/webp"]:
            AvatarImgValidators.validate(self._make_file(content_type=ct))

    def test_validate_invalid_content_type(self):
        file = self._make_file(filename="test.pdf", content_type="application/pdf")
        with self.assertRaises(serializers.ValidationError) as ctx:
            AvatarImgValidators.validate(file)
        self.assertIn("avatar", ctx.exception.detail)

    def test_validate_file_within_size_limit(self):
        file = self._make_file(content=b"x" * (4 * 1024 * 1024))  # 4MB
        AvatarImgValidators.validate(file)

    def test_validate_file_exceeds_size_limit(self):
        file = self._make_file(content=b"x" * (5 * 1024 * 1024 + 1))  # 5MB + 1 byte
        with self.assertRaises(serializers.ValidationError) as ctx:
            AvatarImgValidators.validate(file)
        self.assertIn("avatar", ctx.exception.detail)
