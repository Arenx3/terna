"""Test settings: production settings plus a small tenant app used by the isolation tests."""

from config.settings import *  # noqa: F403
from config.settings import INSTALLED_APPS

INSTALLED_APPS = [*INSTALLED_APPS, "testapp"]
ROOT_URLCONF = "testapp.urls"

# Throttle counters per test, not shared through Redis between runs.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
# Tasks run inline, so emails land in the test outbox.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
# Fast hashing: tests create many users.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Live boards: an in-process channel layer, no Redis needed.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
