from pathlib import Path
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class BaseMediaStorage(S3Boto3Storage):
    signature_version = "s3v4"
    file_overwrite = False
    custom_domain = False
    default_acl = None
    location = ""


class CDNMediaStorage(BaseMediaStorage):
    bucket_name = settings.GARAGE_BUCKET_PUBLIC

    def public_url(self, file_name):
        root_domain = settings.GARAGE_CDN_ROOT_DOMAIN
        port = settings.GARAGE_CDN_PORT
        path = str(Path(self.location) / Path(file_name))
        return f"http://{self.bucket_name}.{root_domain}:{port}/{path}"  # NOSONAR


class S3MediaStorage(BaseMediaStorage):
    bucket_name = settings.GARAGE_BUCKET_AUTH

    def url(self, name, expire):
        import boto3
        from botocore.client import Config

        url = f"http://{settings.GARAGE_S3_HOST}:{settings.GARAGE_S3_PORT}"  # NOSONAR

        client = boto3.client(
            "s3",
            endpoint_url=url,  # public URL for signing
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
