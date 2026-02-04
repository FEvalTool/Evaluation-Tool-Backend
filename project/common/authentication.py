import logging
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, NotFound
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken, UntypedToken
from rest_framework_simplejwt.exceptions import TokenError

from .redis import BaseRedis, RefreshTokenRedis, ScopeTokenRedis
from .scope_token import ScopeToken
from .constants import EventType, ErrorTypes

from users.models import CustomUser

logger = logging.getLogger(__name__)


class CustomTokenAuthentication(BaseAuthentication):
    use_header = False
    cookie_priority = []
    valid_scopes = []
    optional = False

    SCOPE_TOKEN = settings.COOKIE_SETTINGS["AUTH_COOKIE_SCOPE"]
    REFRESH_TOKEN = settings.COOKIE_SETTINGS["AUTH_COOKIE_REFRESH"]
    ACCESS_TOKEN = settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]

    token_properties = {
        REFRESH_TOKEN: {
            "token_class": RefreshToken,
            "redis_class": RefreshTokenRedis,
        },
        SCOPE_TOKEN: {
            "token_class": ScopeToken,
            "redis_class": ScopeTokenRedis,
        },
        ACCESS_TOKEN: {
            "token_class": AccessToken,
            "redis_class": BaseRedis,
        },
    }

    def _get_token_from_cookie(self, request, cookie_priority):
        """
        Extract token from cookie based on cookie priority list

        Parameters
        ----------
        request: HttpRequest
            The HTTP request object.
        cookie_priority: list[str]
            List of cookie name going to extract, order from most
            priority to least one.

        Returns
        -------
        str or None
            The token if found, otherwise None.
        str or None
            Cookie name/Token type, if no token found, return None
        """
        for token_type in cookie_priority:
            token = request.COOKIES.get(token_type)
            if token:
                return token, token_type
        return None, None

    def _get_token_from_header(self, request):
        """
        Extract token from header

        Parameters
        ----------
        request: HttpRequest
            The HTTP request object.

        Returns
        -------
        str or None
            The token if found, otherwise None.
        str or None
            Token type, if token is found, return access token type,
            else, return None
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        parts = auth_header.split()

        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1], settings.COOKIE_SETTINGS["AUTH_COOKIE_ACCESS"]
        return None, None

    def _check_token_validity(self, token, token_type):
        """
        Check if token is valid

        Parameters
        ----------
        token: str
            The jwt token.
        token_type: str
            Type of jwt token (refresh/scope/access).
        Returns
        -------
        AccessToken | RefreshToken | ScopeToken | UntypedToken
            The validate token instance
        """
        redis_class = BaseRedis
        token_class = UntypedToken
        if token_type in self.token_properties:
            redis_class = self.token_properties[token_type]["redis_class"]
            token_class = self.token_properties[token_type]["token_class"]
        token_info = token_class(token)

        jti = token_info["jti"]
        if redis_class.exists(jti):
            raise TokenError("Token is blacklisted")

        return token_info

    def authenticate(self, request):
        token, token_type = None, None

        logger.info(
            {
                "event_type": EventType.AUTHENTICATION_ATTEMP,
                "message": "Begin retrieve token",
            }
        )

        if self.use_header:
            token, token_type = self._get_token_from_header(request)

        if token is None and self.cookie_priority:
            token, token_type = self._get_token_from_cookie(
                request, self.cookie_priority
            )

        if token is None and not self.optional:
            logger.error(
                {
                    "event_type": EventType.AUTHENTICATION_ATTEMP,
                    "error_type": ErrorTypes.TOKEN_NOT_FOUND,
                    "error_content": "No token provided",
                }
            )
            raise NotAuthenticated("No token provided")

        logger.info(
            {
                "event_type": EventType.AUTHENTICATION_ATTEMP,
                "message": f"Retrieve {token_type} token success, begin validate token",
            }
        )

        try:
            payload = self._check_token_validity(token, token_type)
            user = CustomUser.objects.get(id=payload.get("user_id"))
            if token_type == self.SCOPE_TOKEN and len(self.valid_scopes) != 0:
                payload.verify_scope(self.valid_scopes)
            logger.info(
                {
                    "event_type": EventType.AUTHENTICATION_ATTEMP,
                    "message": "Authenticate token success",
                }
            )
            return user, token
        except TokenError as e:
            logger.error(
                {
                    "event_type": EventType.AUTHENTICATION_ATTEMP,
                    "error_type": ErrorTypes.TOKEN_VALIDATION,
                    "error_content": str(e),
                }
            )
            raise AuthenticationFailed(str(e))
        except CustomUser.DoesNotExist:
            logger.error(
                {
                    "event_type": EventType.AUTHENTICATION_ATTEMP,
                    "error_type": ErrorTypes.UNEXISTED,
                    "error_content": f"User with id {payload.get('user_id')} is not existed",
                }
            )
            raise NotFound("Account invalid or deleted")


def configure_auth_class(
    cookie_priority=[], use_header=False, valid_scopes=[], optional=False
):
    """Factory that returns a configured CustomTokenAuthentication subclass."""

    class _Auth(CustomTokenAuthentication):
        pass

    _Auth.cookie_priority = cookie_priority
    _Auth.use_header = use_header
    _Auth.valid_scopes = valid_scopes
    _Auth.optional = optional
    return _Auth
