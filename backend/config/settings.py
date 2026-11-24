"""Django settings for Terna.

Everything comes from the environment (see ``config.env``). The defaults are
safe for local development; ``compose.yaml`` wires the generated secrets.
"""

from pathlib import Path
from urllib.parse import quote

from kombu import Queue

from config.env import env, env_bool, env_int, env_list

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8080")

# nginx always sets X-Forwarded-Proto, overwriting whatever the client sent.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

# Database

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env_int("POSTGRES_PORT", 5432),
        "NAME": env("POSTGRES_DB", "terna"),
        "USER": env("POSTGRES_USER", "terna"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": 3},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Redis: one logical database per use, so a cache flush never drops queued tasks.

REDIS_HOST = env("REDIS_HOST", "localhost")
REDIS_PORT = env_int("REDIS_PORT", 6379)
REDIS_PASSWORD = env("REDIS_PASSWORD", "")


def redis_url(db: int) -> str:
    auth = f":{quote(REDIS_PASSWORD, safe='')}@" if REDIS_PASSWORD else ""
    return f"redis://{auth}{REDIS_HOST}:{REDIS_PORT}/{db}"


REDIS_DB_BROKER = 0
REDIS_DB_CHANNELS = 1
REDIS_DB_CACHE = 2

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": redis_url(REDIS_DB_CACHE),
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [redis_url(REDIS_DB_CHANNELS)]},
    }
}

# API

REST_FRAMEWORK = {
    # Closed by default: every endpoint must opt out explicitly. Authentication arrives with #7.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Terna API",
    "DESCRIPTION": "Applicant tracking with explainable screening and async video interviews.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Swagger UI assets are bundled, so the docs work offline.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
}

# Celery: each worker consumes one queue, so a long transcription never delays an email.

CELERY_BROKER_URL = redis_url(REDIS_DB_BROKER)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_QUEUES = (Queue("default"), Queue("media"), Queue("ml"))
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_IGNORE_RESULT = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULER = "core.beat:HeartbeatScheduler"
CELERY_BEAT_MAX_LOOP_INTERVAL = 30
CELERY_BEAT_SCHEDULE: dict = {}

# Object storage (S3 compatible). The public endpoint is the one browsers reach.

STORAGE_ENDPOINT_URL = env("STORAGE_ENDPOINT_URL", "http://localhost:9000")
STORAGE_PUBLIC_URL = env("STORAGE_PUBLIC_URL", STORAGE_ENDPOINT_URL)
STORAGE_BUCKET = env("STORAGE_BUCKET", "terna")
STORAGE_REGION = env("STORAGE_REGION", "us-east-1")
STORAGE_ACCESS_KEY = env("STORAGE_ACCESS_KEY")
STORAGE_SECRET_KEY = env("STORAGE_SECRET_KEY")

# Email: Mailpit catches everything locally; point these at a real provider to send for real.

EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 1025)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Terna <no-reply@terna.localhost>")

# Internationalization

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
