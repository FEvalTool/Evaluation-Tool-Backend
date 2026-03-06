from django.core.validators import RegexValidator
from rest_framework import serializers
import re


class UserValidators:
    phone_validator = RegexValidator(
        regex=r"^(03[2-9]|05[6|8|9]|07[0-9]|08[1-9]|09[0-9])\d{7}$",
        message="Phone number must be entered in the Vietnamese phone number format.",
    )
    identity_number_validator = RegexValidator(
        regex=r"^(00[1-9]|0[1-9][0-9]|09[0-6])[0-9]{9}$",
        message="Identity number must be entered in the Vietnamese identity nuber format.",
    )

    @staticmethod
    def password_validator(password):
        PASSWORD_FORMAT = (
            r"^(?=.*[a-z])"  # at least one lowercase letter
            r"(?=.*[A-Z])"  # at least one uppercase letter
            r"(?=.*\d)"  # at least one digit
            r"(?=.*[@$!%*?&])"  # at least one special character
            r"[A-Za-z\d@$!%*?&]{12,}$"  # at least 12 characters long
        )
        if re.search(PASSWORD_FORMAT, password) is None:
            raise serializers.ValidationError({"password": "Incorrect password format"})


class AvatarImgValidators:
    MAX_AVATAR_SIZE_MB = 5
    ALLOWED_CONTENT_TYPES = ["image/jpeg", "image/png", "image/webp"]

    @classmethod
    def validate(cls, file):
        if file is None:
            raise serializers.ValidationError({"avatar": "File not found"})
        if file.content_type not in cls.ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(
                {
                    "avatar": f"Invalid file type. Allowed: {', '.join(cls.ALLOWED_CONTENT_TYPES)}"
                }
            )
        if file.size > cls.MAX_AVATAR_SIZE_MB * 1024 * 1024:
            raise serializers.ValidationError(
                {"avatar": f"File too large. Max size is {cls.MAX_AVATAR_SIZE_MB} MB."}
            )
