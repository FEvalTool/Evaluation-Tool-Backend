from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class BaseMediaStorage(S3Boto3Storage):
    signature_version = "s3v4"
    file_overwrite = False
    custom_domain = False
    default_acl = None
    location = ""

    def url(self, name, expire=3600):
        import boto3
        from botocore.client import Config

        client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_PUBLIC_ENDPOINT_URL,  # public URL for signing
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        # Prepend location prefix to the object key
        full_key = f"{self.location}/{name}".lstrip("/")

        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": full_key},
            ExpiresIn=expire,
        )
