from rest_framework import serializers

from ..models import Student


class StudentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Student
        fields = ["id", "first_name", "last_name", "created_date"]


class StudentDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = Student
        fields = "__all__"


class UpdateStudentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Student
        fields = ["first_name", "last_name", "email"]
