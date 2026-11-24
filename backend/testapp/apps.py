from django.apps import AppConfig


class TestAppConfig(AppConfig):
    """Installed only by config.settings_test: a minimal tenant model, API and task
    that exercise tenant isolation end to end, without depending on product models."""

    name = "testapp"
