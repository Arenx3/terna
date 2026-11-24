"""Read configuration from the environment.

Every setting can be given directly (``NAME``) or as a path to a file that
holds it (``NAME_FILE``). Compose uses the file form for the secrets that
``secrets-init`` generates on first start; a direct value always wins.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

_MISSING = object()


def env(name: str, default: str | object = _MISSING) -> str:
    value = os.environ.get(name)
    if value:
        return value

    file_path = os.environ.get(f"{name}_FILE")
    if file_path:
        try:
            return Path(file_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ImproperlyConfigured(f"Cannot read {name}_FILE at {file_path}: {exc}") from exc

    if default is _MISSING:
        raise ImproperlyConfigured(f"Set {name} or {name}_FILE.")
    return default  # type: ignore[return-value]


def env_bool(name: str, default: bool) -> bool:
    value = env(name, "")
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = env(name, "")
    return int(value) if value else default


def env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]
