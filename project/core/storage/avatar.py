from .base import CDNMediaStorage


class AvatarsMediaStorage(CDNMediaStorage):
    location = "media/avatars"


# # Reference: using presigned url instead of public url
# class AvatarsMediaStorage(S3MediaStorage):
#     location = "media/avatars"
#     def url(self, name, expire=7 * 24 * 3600):
#         # Generated 7-days expired presigned url
#         return super().url(name, expire)
