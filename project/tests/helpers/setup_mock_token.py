import jwt
import datetime
import uuid

from rest_framework_simplejwt.settings import api_settings
from django.conf import settings


def create_unknown_user_scope_token(scope="PASSWORD_VERIFY_SCOPE"):
    """
    Create scope token for unknown user
    """
    now = datetime.datetime.utcnow()

    payload = {
        "user_id": 999999,
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
