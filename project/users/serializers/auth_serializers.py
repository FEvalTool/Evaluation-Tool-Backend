from rest_framework import serializers

from .constants import VALID_SECURITY_QA_NUMS


class PasswordVerificationRequest(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class SecurityQAVerificationRequest(serializers.Serializer):
    username = serializers.CharField()
    questions = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=VALID_SECURITY_QA_NUMS,
        max_length=VALID_SECURITY_QA_NUMS,
    )
    answers = serializers.ListField(
        child=serializers.CharField(),
        min_length=VALID_SECURITY_QA_NUMS,
        max_length=VALID_SECURITY_QA_NUMS,
    )

    def validate_questions(self, value):
        # Validate number of questions is exactly equal to 3
        if len(set(value)) != VALID_SECURITY_QA_NUMS:
            raise serializers.ValidationError(
                f"Number of Questions must equals to {VALID_SECURITY_QA_NUMS}"
            )
        return value


class VerifyTokenRequest(serializers.Serializer):
    token_type = serializers.CharField()
