import time
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken
from rest_framework_simplejwt.exceptions import TokenError

from .exceptions import TokenNotFoundException
from .models import CustomUser
from .custom_token import ScopeToken
from .redis.tokens import RefreshTokenRedis, ScopeTokenRedis
from .redis.base import RedisBase


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


def get_token_from_cookie(request, cookie_name, bypass_token_notfound_error):
    """
    Extract token from cookie

    Parameters
    ----------
    request: HttpRequest
        The HTTP request object.
    cookie_name: str
        The name of the cookie to extract the token from.
    bypass_token_notfound_error: bool
        If True, do not raise an error if the token is not found.

    Returns
    -------
    str or None
        The token if found, otherwise None.
    """
    token = request.COOKIES.get(cookie_name)
    if not token and not bypass_token_notfound_error:
        raise TokenNotFoundException(f"Token not found in cookie: {cookie_name}")
    return token


token_properties = {
    "refresh": {
        "token_class": RefreshToken,
        "redis_class": RefreshTokenRedis,
    },
    "scope": {
        "token_class": ScopeToken,
        "redis_class": ScopeTokenRedis,
    },
}


def store_blacklist_token(token, token_type):
    """
    Store blacklisted token in redis

    Parameters
    ----------
    token: str
        The jwt token.
    token_type: int
        Type of jwt token (refresh/scope).

    Returns
    -------
    None
    """
    if token_type not in token_properties:
        raise ValueError("Invalid token type: {}".format(token_type))
    redis_class = token_properties[token_type]["redis_class"]
    token_class = token_properties[token_type]["token_class"]
    token_info = token_class(token)

    current_timestamp = time.time()
    expiration_timestamp = token_info["exp"]

    ttl = int(expiration_timestamp - current_timestamp)
    jti = token_info["jti"]
    redis_class.store(jti, ttl)


def check_token_validity(token, token_type):
    """
    Check if token is blacklisted

    Parameters
    ----------
    token: str
        The jwt token.
    token_type: int
        Type of jwt token (refresh/scope).
    Returns
    -------
    None
    """
    redis_class = RedisBase
    token_class = UntypedToken
    if token_type in token_properties:
        redis_class = token_properties[token_type]["redis_class"]
        token_class = token_properties[token_type]["token_class"]
    # This step also verifies the token validity (e.g., signature, expiration)
    token_info = token_class(token)

    jti = token_info["jti"]
    if redis_class.exists(jti):
        raise TokenError("Token is blacklisted")
