import jwt
from datetime import datetime, timedelta
from django.conf import settings

from .exceptions import TokenValidationException
from .constants import TokenScope
from .models import CustomUser


def generate_username(name):
    """
    Generate username with index

    Parameters
    ----------
    name: str: full name

    Returns
    -------
    str: user name with index

    """
    # Preprocess name have multiple whitespace
    preprocess_name = " ".join(name.split())
    # Getting username prefix (for example Tran Anh Vu => VuTA)
    name_part = preprocess_name.split(" ")
    prefix_username = (
        f"{name_part[-1].capitalize()}{''.join([part[0] for part in name_part[0:-1]])}"
    )
    # Get all user have the same prefix_username
    username_pattern = f"^{prefix_username}(\d+)?$"
    users = CustomUser.objects.filter(username__regex=username_pattern)
    # Return username with index
    return f"{prefix_username}{len(users)+1}"


def create_jwt(data):
    """
    Generate jwt from data

    Parameters
    ----------
    data: dict: payload data

    Returns
    -------
    str: encoded jwt

    """
    payload = {
        **data,
        "exp": datetime.utcnow() + timedelta(minutes=settings.EXPIRES_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_and_verify_jwt(token, verify_function):
    """
    Decode and verify jwt

    Parameters
    ----------
    token: str: jwt token
    verify_function: func: function to verify payload

    Returns
    -------
    dict: decoded payload

    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        verify_function(payload)
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenValidationException("Token expired")
    except jwt.InvalidTokenError as e:
        raise TokenValidationException(f"Invalid token: {e}")


def verify_is_able_to_set_password(payload):
    """
    Function to verify if the user who send payload is verified to set password

    Parameters
    ----------
    payload: dict: payload decoded from jwt

    Returns
    -------
    None

    """
    scope = payload.get("scope", None)
    if scope not in [
        TokenScope.PASSWORD_VERIFY_SCOPE,
        TokenScope.SECURITY_QUESTION_VERIFY_SCOPE,
    ]:
        raise TokenValidationException(f"Invalid scope - {scope}")


def verify_is_able_to_set_security_qa(payload):
    """
    Function to verify if the user who send payload is verified to set security question/answer

    Parameters
    ----------
    payload: dict: payload decoded from jwt

    Returns
    -------
    None

    """
    scope = payload.get("scope", None)
    if scope not in [
        TokenScope.PASSWORD_VERIFY_SCOPE,
    ]:
        raise TokenValidationException(f"Invalid scope - {scope}")
