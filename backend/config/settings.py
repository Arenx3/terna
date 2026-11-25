"""Django settings for Terna.

Everything comes from the environment (see ``config.env``). The defaults are
safe for local development; ``compose.yaml`` wires the generated secrets.
"""

from datetime import timedelta
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
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "core",
    "tenancy",
    "accounts",
    "jobs",
    "events",
    "demo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # API messages follow the Accept-Language header the app sends.
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
]

AUTH_USER_MODEL = "accounts.User"

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
        # Each request is one transaction: the active company (SET LOCAL) lives exactly that long.
        "ATOMIC_REQUESTS": True,
        "OPTIONS": {"connect_timeout": 3},
    }
}

# The unprivileged role the app and workers connect as. Row-level security applies
# to it; only the migration role (POSTGRES_USER of the bootstrap service) bypasses it.
DATABASE_APP_ROLE = env("POSTGRES_APP_USER", "terna_app")

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
    # Closed by default: every endpoint must opt out explicitly.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.exceptions.exception_handler",
    "UNAUTHENTICATED_USER": None,
    # Per client IP (IPRateThrottle) and per target address (EmailRateThrottle).
    "DEFAULT_THROTTLE_RATES": {
        # Overridable so end-to-end runs, which sign up repeatedly, are not throttled.
        "signup": env("AUTH_SIGNUP_RATE", "5/hour"),
        "login": "20/min",
        "login_email": "5/min",
        "refresh": "60/min",
        "verify_email": "30/hour",
        "resend_verification": "10/hour",
        "resend_verification_email": "3/hour",
        "password_reset": "10/hour",
        "password_reset_email": "3/hour",
        "password_reset_confirm": "20/hour",
        "invite": "50/hour",
        "invitation": "60/hour",
    },
}

# Authentication

SIMPLE_JWT = {
    # Short-lived and kept in memory by the app; carries the active company.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    # In an httpOnly cookie, single use: every refresh rotates it.
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}
AUTH_REFRESH_COOKIE = "terna_refresh"
AUTH_REFRESH_COOKIE_PATH = "/api/auth/"
# Set to true behind HTTPS. Plain HTTP on localhost needs it off.
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", False)

EMAIL_VERIFICATION_MAX_AGE = int(timedelta(days=3).total_seconds())
PASSWORD_RESET_TIMEOUT = int(timedelta(hours=2).total_seconds())

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("email", "full_name")},
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Base URL of the web app, used in links sent by email.
PUBLIC_APP_URL = env("PUBLIC_APP_URL", "http://localhost:8080")

SPECTACULAR_SETTINGS = {
    "TITLE": "Terna API",
    "DESCRIPTION": "Applicant tracking with explainable screening and async video interviews.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Separate request and response shapes, so clients never have to send read-only fields.
    "COMPONENT_SPLIT_REQUEST": True,
    # Swagger UI assets are bundled, so the docs work offline.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    # Two fields are called "status"; name their enums explicitly.
    "ENUM_NAME_OVERRIDES": {
        "HealthStatusEnum": "core.serializers.STATUS_CHOICES",
        "InvitationStatusEnum": "accounts.serializers.INVITATION_STATUSES",
        "JobStatusEnum": "jobs.models.Job.Status",
        "RequirementKindEnum": "jobs.models.Requirement.Kind",
        "StageKindEnum": "jobs.models.StageKind",
        "EventTypeEnum": "events.models.EventType",
    },
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
CELERY_BEAT_SCHEDULE: dict = {
    # Safety net for the transactional outbox: events whose kick was lost still go out.
    "dispatch-outbox": {"task": "events.tasks.dispatch_outbox", "schedule": 30.0},
}

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
LANGUAGES = [("en", "English"), ("es", "Español")]
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
