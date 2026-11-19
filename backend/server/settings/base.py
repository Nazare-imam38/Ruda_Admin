
"""Shared configuration for the isolated GIS Automation Lab."""

import os
from pathlib import Path

from dotenv import load_dotenv

# backend directory
BASE_DIR = Path(__file__).resolve().parents[2]

# Load local environment variables from backend/.env
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "unsafe-gis-lab-local-only",
)

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "api.apps.LayersConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "server.urls"
WSGI_APPLICATION = "server.wsgi.application"
ASGI_APPLICATION = "server.asgi.application"

TEMPLATES = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "gis_automation_test"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

# Safety: this project must never connect to the RUDA database.
if DATABASES["default"]["NAME"] != "gis_automation_test":
    raise RuntimeError(
        "This lab only permits the gis_automation_test database. "
        "Do not point it at RUDA."
    )

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

DATA_UPLOAD_MAX_MEMORY_SIZE = 45 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
