from .base import *

# Retrieve public/private key from folder and set RS256 algorithm to simplejwt
private_key_file = "{}/security/jwtRS256.key".format(BASE_DIR)
with open(private_key_file, "r") as content_file:
    private_key = content_file.read()

public_key_file = "{}/security/jwtRS256.key.pub".format(BASE_DIR)
with open(public_key_file, "r") as content_file:
    public_key = content_file.read()

SIMPLE_JWT = {
    "ROTATE_REFRESH_TOKENS": True,
    "ALGORITHM": "RS256",
    "VERIFYING_KEY": public_key,
    "SIGNING_KEY": private_key,
}

# CORS setting
CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://.*\.eduscrum\.local:\d+$",
]
CORS_ALLOW_METHODS = ["POST", "GET", "PATCH", "PUT", "OPTIONS", "DELETE"]
ALLOWED_HOSTS = ["user-backend", "api.auth.eduscrum.local"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "content-type",
    "authorization",
    "access-control-allow-methods",
    "access-control-allow-origin",
    "access-control-allow-headers",
]
