from django_redis import get_redis_connection


class RedisBase:
    PREFIX = ""

    @classmethod
    def _redis(cls):
        return get_redis_connection("default")

    @classmethod
    def _key(cls, jti: str) -> str:
        return f"{cls.PREFIX}:{jti}"

    @classmethod
    def store(cls, jti: str, ttl: int):
        cls._redis().set(cls._key(jti), 1, ex=ttl)

    @classmethod
    def exists(cls, jti: str) -> bool:
        return cls._redis().exists(cls._key(jti)) == 1

    @classmethod
    def delete(cls, jti: str):
        cls._redis().delete(cls._key(jti))
