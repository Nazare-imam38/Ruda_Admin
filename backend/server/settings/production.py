
"""Production settings."""

from .base import *

DEBUG = False

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

if not ALLOWED_HOSTS:
    raise RuntimeError(
        "Set DJANGO_ALLOWED_HOSTS before running production settings."
    )

# Require HTTPS in production.
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
