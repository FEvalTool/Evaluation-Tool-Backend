class TokenScope:
    PASSWORD_VERIFY_SCOPE = "PASSWORD_VERIFY_SCOPE"
    SECURITY_QUESTION_VERIFY_SCOPE = "SECURITY_QUESTION_VERIFY_SCOPE"


class EventType:
    CREATE_USER_ACCOUNT = "CREATE_USER_ACCOUNT"
    LOGIN = "LOGIN"
    SET_PASSWORD = "SET_PASSWORD"
    SET_SECURITY_QA = "SET_SECURITY_QA"
    GET_USER_SECURITY_QUESTIONS = "GET_USER_SECURITY_QUESTIONS"
    GENERATE_VERIFICATION_TOKEN = "GENERATE_VERIFICATION_TOKEN"
    VERIFY_TOKEN = "VERIFY_TOKEN"
    REFRESH_TOKEN = "REFRESH_TOKEN"
    DELETE_SCOPE_TOKEN = "DELETE_SCOPE_TOKEN"
    LOGOUT = "LOGOUT"
    CREATE_SECURITY_QUESTIONS = "CREATE_SECURITY_QUESTIONS"
    LIST_SECURITY_QUESTIONS = "LIST_SECURITY_QUESTIONS"


PASSWORD_FORMAT = (
    r"^(?=.*[a-z])"  # at least one lowercase letter
    r"(?=.*[A-Z])"  # at least one uppercase letter
    r"(?=.*\d)"  # at least one digit
    r"(?=.*[@$!%*?&])"  # at least one special character
    r"[A-Za-z\d@$!%*?&]{12,}$"  # at least 12 characters long
)

VALID_SECURITY_QA_NUMS = 3

BYPASS_TOKEN_NOTFOUND = "bypass_token_notfound_error"
