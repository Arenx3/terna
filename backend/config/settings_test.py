"""Test settings: production settings plus a small tenant app used by the isolation tests."""

from config.settings import *  # noqa: F403
from config.settings import INSTALLED_APPS

INSTALLED_APPS = [*INSTALLED_APPS, "testapp"]
ROOT_URLCONF = "testapp.urls"
