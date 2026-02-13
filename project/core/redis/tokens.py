from .base import BaseRedis


class RefreshTokenRedis(BaseRedis):
    PREFIX = "refresh"


class ScopeTokenRedis(BaseRedis):
    PREFIX = "scope"
