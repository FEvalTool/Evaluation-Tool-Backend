import jwt
import datetime
import uuid

from rest_framework_simplejwt.settings import api_settings
from django.conf import settings

from users.constants import TokenScope
from users.models import CustomUser


class TokenFactory:
    @staticmethod
    def valid_token():
        valid_user = CustomUser.objects.get(username="testuser1")
        return create_scope_token(
            user_id=valid_user.id, scope=TokenScope.PASSWORD_VERIFY_SCOPE
        )

    @staticmethod
    def unknown_user():
        return create_scope_token(user_id=99999, scope=TokenScope.PASSWORD_VERIFY_SCOPE)

    @staticmethod
    def wrong_scope():
        valid_user = CustomUser.objects.get(username="testuser1")
        return create_scope_token(user_id=valid_user.id, scope="WRONG_SCOPE")

    @staticmethod
    def invalid_signature():
        return "invalid.token.string"


def create_scope_token(user_id, scope="PASSWORD_VERIFY_SCOPE"):
    """
    Create scope token
    """
    now = datetime.datetime.utcnow()

    payload = {
        "user_id": user_id,
        "token_type": settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
        "scope": scope,
        "exp": now + settings.SCOPE_TOKEN_LIFETIME_MINUTES,
        "iat": now,
        "jti": uuid.uuid4().hex,
    }

    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=api_settings.ALGORITHM,
    )

    return token
