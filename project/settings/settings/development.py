from .base import *


CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://.*\.eduscrum\.local:\d+$",
]
CORS_ALLOW_METHODS = ["POST", "GET", "PATCH", "PUT", "OPTIONS"]
ALLOWED_HOSTS = ["user-backend", "api.auth.eduscrum.local"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "content-type",
    "authorization",
    "access-control-allow-methods",
    "access-control-allow-origin",
    "access-control-allow-headers",
]
