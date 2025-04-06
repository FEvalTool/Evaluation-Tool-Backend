from django.urls import path

from ..views.student_views import (
    StudentView,
    StudentDetailView,
)

urlpatterns = [
    path("", StudentView.as_view(), name="student"),
    path("<str:pk>/", StudentDetailView.as_view(), name="student-detail"),
]
