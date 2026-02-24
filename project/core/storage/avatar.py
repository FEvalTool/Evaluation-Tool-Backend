from .base import BaseMediaStorage


class AvatarsMediaStorage(BaseMediaStorage):
    location = "media/avatars"

    def url(self, name, expire=7 * 24 * 3600):
        # Generated 7-days expired presigned url
        return super().url(name, expire)
