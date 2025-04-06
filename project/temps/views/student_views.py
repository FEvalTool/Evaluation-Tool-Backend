from django.core.paginator import Paginator, EmptyPage
from django.db import transaction
from django.http import JsonResponse
from rest_framework import serializers, status
from rest_framework.views import APIView

from ..models import Student
from ..utils import get_sort_query
from ..constants import VALIDATION_ERROR, INTERNAL_SERVER_ERROR, DOES_NOT_EXIST_ERROR
from ..serializers.query_params_serializers import QueryParamsSerializer
from ..serializers.student_serializers import (
    StudentSerializer,
    StudentDetailSerializer,
    UpdateStudentSerializer,
)


class StudentView(APIView):
    def get(self, request):
        try:
            query_serializer = QueryParamsSerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return JsonResponse(
                    {
                        "message_type": VALIDATION_ERROR,
                        "error-content": query_serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sort_query = get_sort_query(
                model=Student, request_query_params=query_serializer.data
            )
            students = Student.objects.all()
            if len(sort_query):
                students = students.order_by(*sort_query)
            student_serializer = StudentSerializer(students, many=True)
            if query_serializer.data["all"]:
                result = student_serializer.data
            else:
                paginator = Paginator(
                    student_serializer.data, query_serializer.data["page_size"]
                )
                result = paginator.page(query_serializer.data["page_index"])
                result = result.object_list
            return JsonResponse({"result": result})
        except EmptyPage:
            result = paginator.page(paginator.num_pages)
            result = result.object_list
            return JsonResponse({"result": result})
        except Exception as e:
            return JsonResponse(
                {
                    "message_type": INTERNAL_SERVER_ERROR,
                    "error-content": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @transaction.atomic
    def post(self, request):
        try:
            serializer = StudentDetailSerializer(data=request.data)
            if not serializer.is_valid():
                return JsonResponse(
                    {
                        "message_type": VALIDATION_ERROR,
                        "error-content": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            student = Student.objects.create(**serializer.data)
            return JsonResponse(StudentDetailSerializer(student).data)
        except Exception as e:
            transaction.set_rollback(True)
            return JsonResponse(
                {
                    "message_type": INTERNAL_SERVER_ERROR,
                    "error-content": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StudentDetailView(APIView):
    def get(self, request, pk):
        try:
            result = Student.objects.get(pk=pk)
            return JsonResponse(StudentDetailSerializer(result).data)
        except Student.DoesNotExist:
            return JsonResponse(
                {
                    "message_type": DOES_NOT_EXIST_ERROR,
                    "error-content": f"Student with id = {pk} does not exist",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return JsonResponse(
                {
                    "message_type": INTERNAL_SERVER_ERROR,
                    "error-content": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @transaction.atomic
    def put(self, request, pk):
        try:
            student = Student.objects.get(pk=pk)
            serializer = UpdateStudentSerializer(data=request.data)
            if not serializer.is_valid():
                return JsonResponse(
                    {
                        "message_type": VALIDATION_ERROR,
                        "error-content": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for field, value in serializer.data.items():
                setattr(student, field, value)
            student.save()
            return JsonResponse(StudentDetailSerializer(student).data)
        except Student.DoesNotExist:
            return JsonResponse(
                {
                    "message_type": DOES_NOT_EXIST_ERROR,
                    "error-content": f"Student with id = {pk} does not exist",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            transaction.set_rollback(True)
            return JsonResponse(
                {
                    "message_type": INTERNAL_SERVER_ERROR,
                    "error-content": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @transaction.atomic
    def delete(self, resquest, pk):
        try:
            student = Student.objects.get(pk=pk)
            student.delete()
            return JsonResponse(data={}, status=status.HTTP_204_NO_CONTENT)
        except Student.DoesNotExist:
            return JsonResponse(
                {
                    "message_type": DOES_NOT_EXIST_ERROR,
                    "error-content": f"Student with id = {pk} does not exist",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            transaction.set_rollback(True)
            return JsonResponse(
                {
                    "message_type": INTERNAL_SERVER_ERROR,
                    "error-content": str(e),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
