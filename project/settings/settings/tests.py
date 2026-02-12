from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from .base import *

# When testing, we do not care about frontend related setting (CORS)


# Generate public/private key and set RS256 algorithm to simplejwt
def generate_test_keys():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem.decode(), public_pem.decode()


PRIVATE_KEY, PUBLIC_KEY = generate_test_keys()

SIMPLE_JWT = {
    "ROTATE_REFRESH_TOKENS": True,
    "ALGORITHM": "RS256",
    "SIGNING_KEY": PRIVATE_KEY,
    "VERIFYING_KEY": PUBLIC_KEY,
}
