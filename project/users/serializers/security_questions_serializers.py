from rest_framework import serializers

from ..models import SecurityQuestion, Status


class CreateSecurityQuestionRequest(serializers.Serializer):
    content = serializers.CharField()


class SecurityQuestionSearchParam(serializers.Serializer):
    status = serializers.ChoiceField(choices=Status.choices, required=False)


class SecurityQuestionListResponse(serializers.ModelSerializer):
    class Meta:
        model = SecurityQuestion
        fields = "__all__"
