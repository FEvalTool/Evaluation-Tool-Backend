import time
from django.conf import settings
from rest_framework.exceptions import NotAuthenticated
from rest_framework_simplejwt.exceptions import TokenError
from ..redis import BaseRedis, RefreshTokenRedis, ScopeTokenRedis
from .tokens import ScopeToken, AccessToken, RefreshToken, UntypedToken
from .constants import ACCESS_TOKEN, REFRESH_TOKEN, SCOPE_TOKEN


TOKEN_PROPERTIES = {
    ACCESS_TOKEN: {
        "token_class": AccessToken,
        "redis_class": BaseRedis,
    },
    REFRESH_TOKEN: {
        "token_class": RefreshToken,
        "redis_class": RefreshTokenRedis,
    },
    SCOPE_TOKEN: {
        "token_class": ScopeToken,
        "redis_class": ScopeTokenRedis,
    },
}


def get_token_from_cookies(request, cookie_priority):
    """
    Extract token from cookies based on priority list.

    Parameters
    ----------
    request: HttpRequest
        The HTTP request object.
    cookie_priority: list[str]
        List of cookie names in priority order (most to least priority).

    Returns
    -------
    tuple[str | None, str | None]
        (token, token_type) if found, otherwise (None, None).
    """
    for token_type in cookie_priority:
        token = request.COOKIES.get(token_type)
        if token:
            return token, token_type
    return None, None


def get_token_from_cookie(request, cookie_name, raise_if_missing=True):
    """
    Extract token from a specific cookie.

    Parameters
    ----------
    request: HttpRequest
        The HTTP request object.
    cookie_name: str
        The name of the cookie.
    raise_if_missing: bool
        If True, raise NotAuthenticated if token not found.

    Returns
    -------
    str | None
        The token if found, otherwise None (or raises exception).
    """
    token = request.COOKIES.get(cookie_name)
    if not token and raise_if_missing:
        raise NotAuthenticated(f"Token not found in cookie: {cookie_name}")
    return token


def get_token_from_header(request):
    """
    Extract Bearer token from Authorization header.

    Parameters
    ----------
    request: HttpRequest
        The HTTP request object.

    Returns
    -------
    tuple[str | None, str | None]
        (token, token_type) if found. Token type is always ACCESS_TOKEN for headers.
        Returns (None, None) if not found.
    """
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    parts = auth_header.split()

    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1], ACCESS_TOKEN
    return None, None


def check_token_validity(token, token_type):
    """
    Validate token and check if it's blacklisted.

    Parameters
    ----------
    token: str
        The JWT token string.
    token_type: str
        Type of JWT token (refresh/scope/access).

    Returns
    -------
    AccessToken | RefreshToken | ScopeToken | UntypedToken
        The validated token instance.

    Raises
    ------
    TokenError
        If token is invalid, expired, or blacklisted.
    """
    redis_class = BaseRedis
    token_class = UntypedToken

    if token_type in TOKEN_PROPERTIES:
        redis_class = TOKEN_PROPERTIES[token_type]["redis_class"]
        token_class = TOKEN_PROPERTIES[token_type]["token_class"]

    # This validates signature, expiration, etc.
    token_info = token_class(token)

    # Check blacklist
    jti = token_info["jti"]
    if redis_class.exists(jti):
        raise TokenError("Token is blacklisted")

    return token_info


def store_blacklist_token(token, token_type):
    """
    Blacklist a token by storing its JTI in Redis with TTL matching token expiration.

    Parameters
    ----------
    token: str
        The JWT token string to blacklist.
    token_type: str
        Type of JWT token (must be one of: 'refresh', 'scope', 'access').

    Raises
    ------
    ValueError
        If token_type is not recognized.
    TokenError
        If token is invalid, expired, or malformed.

    Notes
    -----
    The token is stored in Redis with a TTL that matches the token's remaining
    lifetime, so it automatically expires from the blacklist when the token
    would have expired anyway.
    """
    if token_type not in TOKEN_PROPERTIES:
        raise ValueError(
            f"Invalid token_type '{token_type}'. "
            f"Must be one of: {', '.join(TOKEN_PROPERTIES.keys())}"
        )

    redis_class = TOKEN_PROPERTIES[token_type]["redis_class"]
    token_class = TOKEN_PROPERTIES[token_type]["token_class"]

    # This will raise TokenError if token is invalid/expired
    token_info = token_class(token)

    current_timestamp = time.time()
    expiration_timestamp = token_info["exp"]

    ttl = int(expiration_timestamp - current_timestamp)

    # Only store if TTL is positive (token hasn't expired yet)
    if ttl > 0:
        jti = token_info["jti"]
        redis_class.store(jti, ttl)


def set_auth_cookies(response, cookies):
    """
    Set authentication cookies on a response with security settings.

    Applies project-wide auth cookie security configuration (httponly, secure,
    samesite, path) to each cookie. Used for setting refresh tokens, scope tokens,
    and other auth-related cookies.

    Parameters
    ----------
    response : rest_framework.response.Response
        The DRF response object to attach cookies to.
    cookies : list[dict]
        List of cookie definitions. Each dict must contain:
        - 'key': str - Cookie name
        - 'value': str - Cookie value (typically a JWT token)
        - 'max_age': int - Cookie lifetime in seconds

    Returns
    -------
    rest_framework.response.Response
        The response object with cookies attached.

    Examples
    --------
    >>> cookies = [
    ...     {'key': 'refresh_token', 'value': str(refresh), 'max_age': 86400},
    ...     {'key': 'scope_token', 'value': str(scope), 'max_age': 3600}
    ... ]
    >>> response = Response({'message': 'Login successful'})
    >>> set_auth_cookies(response, cookies)
    """
    for cookie in cookies:
        response.set_cookie(
            key=cookie["key"],
            value=cookie["value"],
            max_age=cookie["max_age"],
            secure=settings.COOKIE_SETTINGS["AUTH_COOKIE_SECURE"],
            httponly=settings.COOKIE_SETTINGS["AUTH_COOKIE_HTTP_ONLY"],
            samesite=settings.COOKIE_SETTINGS["AUTH_COOKIE_SAMESITE"],
            path=settings.COOKIE_SETTINGS["AUTH_COOKIE_PATH"],
        )
    return response
