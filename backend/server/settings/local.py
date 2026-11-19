
"""Local development settings."""

from .base import *

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "backend",
]
