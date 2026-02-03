from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from .validators import UserValidators


class CustomUser(AbstractBaseUser, PermissionsMixin):
    GLOBAL_ROLES = [
        ("user", "Regular User"),
        ("staff", "Staff Member"),
        ("superadmin", "Super Administrator"),
    ]

    username = models.CharField(
        max_length=150,
        unique=True,
        help_text="A unique identifier that you will use to log in",
    )
    name = models.CharField(
        max_length=150, help_text="Your full name as it appears in official documents"
    )
    phone_number = models.CharField(
        validators=[UserValidators.phone_validator],
        max_length=10,
        help_text="Your telephone number",
    )
    dob = models.DateField(help_text="Your birthday")
    identity_number = models.CharField(
        validators=[UserValidators.identity_number_validator],
        max_length=12,
        help_text="Your identity number",
    )
    is_active = models.BooleanField(default=True, help_text="Is this user active")
    date_joined = models.DateTimeField(
        default=timezone.now, help_text="User joined date"
    )
    is_default_password = models.BooleanField(
        default=True,
        help_text="Is this user using the default password",
    )
    is_security_question_set = models.BooleanField(
        default=False, help_text="Is this user set the security question answer"
    )
    global_role = models.CharField(
        max_length=20,
        choices=GLOBAL_ROLES,
        default="user",
        help_text="Global role for user",
    )
    USERNAME_FIELD = "username"

    def __str__(self):
        return self.username


class Status(models.TextChoices):
    unofficial = "Unofficial", "Unofficial"
    official = "Official", "Official"
    outdated = "Outdated", "Outdated"


class SecurityQuestion(models.Model):
    """
    List of security question
    """

    content = models.TextField(
        help_text="Security question",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.unofficial,
        help_text="Question status",
    )


class UserQuestionAnswer(models.Model):
    """
    User Security Question/Answer
    """

    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="security_qa_user"
    )
    question = models.ForeignKey(
        SecurityQuestion, on_delete=models.CASCADE, related_name="security_qa_question"
    )
    answer = models.TextField(
        help_text="Answer to the security question used for password update",
    )
