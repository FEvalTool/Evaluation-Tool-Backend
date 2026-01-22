from users.models import CustomUser, SecurityQuestion, UserQuestionAnswer

NEW_USER_USERNAME = "new_user"
NEW_USER_PASSWORD = "correctpassword"
ACTIVE_USER_USERNAME = "active_user"
ACTIVE_USER_PASSWORD = "cORRectPassw0rd!"


def create_test_users():
    """
    Create and return two users:
    - new_user: has default password and no security questions set
    - active_user: has password and security questions set
    """
    user_info_list = [
        {
            "username": NEW_USER_USERNAME,
            "name": "New User",
            "phone_number": "0123456789",
            "dob": "1990-01-01",
            "identity_number": "123456789012",
        },
        {
            "username": ACTIVE_USER_USERNAME,
            "name": "Active User",
            "phone_number": "0987654321",
            "dob": "2000-01-01",
            "identity_number": "123456789999",
            "is_default_password": False,
            "is_security_question_set": True,
        },
    ]

    new_user = CustomUser(**user_info_list[0])
    new_user.set_password(NEW_USER_PASSWORD)
    active_user = CustomUser(**user_info_list[1])
    active_user.set_password(ACTIVE_USER_PASSWORD)
    new_user.save()
    active_user.save()

    return new_user, active_user


def create_security_questions():
    """Create and return all official security questions."""
    question_list = [
        {"content": "What is your mother's maiden name?", "status": "Official"},
        {"content": "What is your pet's name?", "status": "Official"},
        {"content": "What was the name of your first school?", "status": "Official"},
        {
            "content": "What was your favorite spot in your hometown?",
            "status": "Unofficial",
        },
    ]
    SecurityQuestion.objects.bulk_create(
        [SecurityQuestion(**data) for data in question_list]
    )
    return SecurityQuestion.objects.all().order_by("content")


def create_user_question_answers(user, questions):
    """Link a given user with security question answers."""
    answer_list = [
        {"user": user, "question": questions[0], "answer": "Smith"},
        {"user": user, "question": questions[1], "answer": "Fluffy"},
        {"user": user, "question": questions[2], "answer": "Greenwood"},
    ]
    UserQuestionAnswer.objects.bulk_create(
        [UserQuestionAnswer(**data) for data in answer_list]
    )


def setup_mock_accounts():
    """Setup mock accounts for testing."""
    _, active_user = create_test_users()
    security_questions = list(create_security_questions())
    create_user_question_answers(active_user, security_questions)
