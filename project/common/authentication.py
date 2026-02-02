from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, NotFound
from rest_framework.authentication import BaseAuthentication

from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import TokenError

from users.models import CustomUser


class CustomTokenAuthentication(BaseAuthentication):
    use_header = False
    cookie_priority = []
    optional = False

    def _get_token_from_cookie(self, request, cookie_priority):
        for cookie_name in cookie_priority:
            token = request.COOKIES.get(cookie_name)
            if token:
                return token
        return None

    def _get_token_from_header(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        parts = auth_header.split()

        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return None

    def authenticate(self, request):
        token = None

        if self.use_header:
            token = self._get_token_from_header(request)

        if token is None and self.cookie_priority:
            token = self._get_token_from_cookie(request, self.cookie_priority)

        if token is None:
            if self.optional:
                return None
            raise NotAuthenticated("No token provided")

        try:
            payload = UntypedToken(token)
            user = CustomUser.objects.get(id=payload.get("user_id"))
            return user, token
        except TokenError as e:
            raise AuthenticationFailed(str(e))
        except CustomUser.DoesNotExist:
            raise NotFound("Account invalid or deleted")


def configure_auth_class(cookie_priority=[], use_header=False, optional=False):
    """Factory that returns a configured CustomTokenAuthentication subclass."""

    class _Auth(CustomTokenAuthentication):
        pass

    _Auth.cookie_priority = cookie_priority
    _Auth.use_header = use_header
    _Auth.optional = optional
    return _Auth
