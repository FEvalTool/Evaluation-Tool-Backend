from users.models import CustomUser, SecurityQuestion, UserQuestionAnswer


def create_test_users():
    """
    Create and return two users:
    - first_time_setup_user: has default password and no security questions set
    - normal_user: has password and security questions set
    """
    user_info_list = [
        {
            "username": "testuser",
            "name": "Test User",
            "phone_number": "0123456789",
            "dob": "1990-01-01",
            "identity_number": "123456789012",
        },
        {
            "username": "testuser1",
            "name": "Test User 1",
            "phone_number": "0987654321",
            "dob": "2000-01-01",
            "identity_number": "123456789999",
            "is_default_password": False,
            "is_security_question_set": True,
        },
    ]

    first_time_setup_user = CustomUser(**user_info_list[0])
    first_time_setup_user.set_password("correctpassword")
    normal_user = CustomUser(**user_info_list[1])
    normal_user.set_password("cORRectPassw0rd!")
    first_time_setup_user.save()
    normal_user.save()

    return first_time_setup_user, normal_user


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
    _, normal_user = create_test_users()
    security_questions = list(create_security_questions())
    create_user_question_answers(normal_user, security_questions)
