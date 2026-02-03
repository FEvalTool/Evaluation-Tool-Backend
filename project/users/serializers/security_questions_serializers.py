from rest_framework import serializers

from ..models import SecurityQuestion, Status


class CreateSecurityQuestionSerializer(serializers.Serializer):
    content = serializers.CharField()


class SecurityQuestionQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Status.choices, required=False)


class SecurityQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityQuestion
        fields = "__all__"
