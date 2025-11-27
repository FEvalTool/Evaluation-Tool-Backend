from django.conf import settings
from rest_framework_simplejwt.tokens import Token
from rest_framework_simplejwt.exceptions import TokenError


class ScopeToken(Token):
    token_type = "scope"
    lifetime = settings.SCOPE_TOKEN_LIFETIME

    @classmethod
    def for_user(cls, user, scope):
        """Add scope property for scope token"""
        token = super().for_user(user)
        token["scope"] = scope
        return token

    def verify_scope(self, expected_scopes):
        """Verify that the token's scope is in the expected scopes."""
        actual_scope = self.get("scope", None)
        if actual_scope not in expected_scopes:
            raise TokenError("Token scope mismatch")
