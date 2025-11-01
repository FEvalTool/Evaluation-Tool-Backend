from rest_framework import serializers
from .constants import VALID_SECURITY_QA_NUMS
from .validators import UserValidators
from .models import CustomUser, SecurityQuestion


class InitAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["name", "phone_number", "dob", "identity_number"]


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class SetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(validators=[UserValidators.password_validator])


class SetSecurityQASerializer(serializers.Serializer):
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
        # Validate questions are existed in db
        questions_from_db = SecurityQuestion.objects.filter(
            id__in=value, status="Official"
        )
        if len(questions_from_db) != len(value):
            raise serializers.ValidationError("Non-exist questions")
        # Reorder the question instances based on question id (value)
        id_to_instance = {q.id: q for q in questions_from_db}
        ordered_questions = [id_to_instance[qid] for qid in value]
        return ordered_questions


class GetSecurityQuestionParamsSerializer(serializers.Serializer):
    username = serializers.CharField()


class GetSecurityQAVerificationTokenSerializer(serializers.Serializer):
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
