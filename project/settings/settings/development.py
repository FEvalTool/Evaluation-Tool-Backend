from .base import *

CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
CORS_ALLOW_METHODS = ["POST", "GET", "PATCH", "PUT", "OPTIONS"]
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "user-backend"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "content-type",
    "authorization",
    "access-control-allow-methods",
    "access-control-allow-origin",
    "access-control-allow-headers",
]
