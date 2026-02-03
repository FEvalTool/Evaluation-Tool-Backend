from .base import RedisBase


class RefreshTokenRedis(RedisBase):
    PREFIX = "refresh"


class ScopeTokenRedis(RedisBase):
    PREFIX = "scope"
