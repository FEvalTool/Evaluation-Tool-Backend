import jwt
import datetime
import uuid

from rest_framework_simplejwt.settings import api_settings
from django.conf import settings

from users.models import CustomUser

exp_per_token_type = {
    settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]: settings.SCOPE_TOKEN_LIFETIME,
    settings.COOKIE_SETTINGS[
        "AUTH_COOKIE_REFRESH"
    ]: api_settings.REFRESH_TOKEN_LIFETIME,
    settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]: api_settings.ACCESS_TOKEN_LIFETIME,
}


class TokenFactory:
    """Class to generate token for testing"""

    @staticmethod
    def valid_token(token_type, username, scope=None):
        valid_user = CustomUser.objects.get(username=username)
        return create_token(user_id=valid_user.id, token_type=token_type, scope=scope)

    @staticmethod
    def unknown_user(token_type, scope=None):
        return create_token(user_id=99999, token_type=token_type, scope=scope)

    @staticmethod
    def wrong_scope():
        valid_user = CustomUser.objects.get(username="testuser1")
        return create_token(
            user_id=valid_user.id,
            token_type=settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"],
            scope="WRONG_SCOPE",
        )

    @staticmethod
    def invalid_signature():
        return "invalid.token.string"


def create_token(user_id, token_type, scope):
    now = datetime.datetime.utcnow()

    payload = {
        "user_id": user_id,
        "token_type": token_type,
        "exp": now + exp_per_token_type.get(token_type, 0),
        "iat": now,
        "jti": uuid.uuid4().hex,
    }
    if scope:
        payload["scope"] = scope
    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=api_settings.ALGORITHM,
    )
    return token


def get_jti_from_jwt(token):
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[api_settings.ALGORITHM],
    )
    jti = payload.get("jti")
    return str(jti)
