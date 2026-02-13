import logging
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, NotFound
from rest_framework_simplejwt.exceptions import TokenError
from users.models import CustomUser
from .utils import (
    get_token_from_cookies,
    get_token_from_header,
    check_token_validity,
)
from .constants import SCOPE_TOKEN
from ..constants import EventType, ErrorTypes

logger = logging.getLogger(__name__)


class CustomTokenAuthentication(BaseAuthentication):
    """
    Flexible JWT token authentication supporting multiple token sources.

    Attributes
    ----------
    use_header: bool
        Whether to check Authorization header for Bearer tokens.
    cookie_priority: list[str]
        List of cookie names to check in priority order.
    valid_scopes: list[str]
        Required scopes for scope tokens (empty list = no scope validation).
    optional: bool
        If True, allow requests without tokens (user will be None).
    """

    use_header = False
    cookie_priority = []
    valid_scopes = []
    optional = False

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response.
        DRF uses the presence of this to decide between 401 and 403.
        """
        return "Bearer"

    def authenticate(self, request):
        token, token_type = None, None

        logger.info(
            {
                "event_type": EventType.AUTHENTICATION_ATTEMP,
                "message": "Begin retrieve token",
            }
        )

        # Try header first if enabled
        if self.use_header:
            token, token_type = get_token_from_header(request)

        # Fall back to cookies
        if token is None and self.cookie_priority:
            token, token_type = get_token_from_cookies(request, self.cookie_priority)

        # No token found
        if token is None:
            if self.optional:
                return None, None
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
                "message": f"Retrieved {token_type} token, validating",
            }
        )

        # Validate token
        try:
            payload = check_token_validity(token, token_type)
            user = CustomUser.objects.get(id=payload.get("user_id"))

            # Verify scope if it's a scope token with required scopes
            if token_type == SCOPE_TOKEN and self.valid_scopes:
                payload.verify_scope(self.valid_scopes)

            logger.info(
                {
                    "event_type": EventType.AUTHENTICATION_ATTEMP,
                    "message": "Authentication successful",
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
                    "error_content": f"User with id {payload.get('user_id')} does not exist",
                }
            )
            raise NotFound("Account invalid or deleted")


def configure_auth(
    cookie_priority=None, use_header=False, valid_scopes=None, optional=False
):
    """
    Factory function to create configured authentication classes.

    Parameters
    ----------
    cookie_priority: list[str] | None
        Cookie names in priority order.
    use_header: bool
        Whether to check Authorization header.
    valid_scopes: list[str] | None
        Required scopes for scope tokens.
    optional: bool
        Allow unauthenticated requests.

    Returns
    -------
    type
        Configured CustomTokenAuthentication subclass.
    """

    class _ConfiguredAuth(CustomTokenAuthentication):
        pass

    _ConfiguredAuth.cookie_priority = cookie_priority or []
    _ConfiguredAuth.use_header = use_header
    _ConfiguredAuth.valid_scopes = valid_scopes or []
    _ConfiguredAuth.optional = optional

    return _ConfiguredAuth
