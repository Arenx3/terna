import pytest
from django.core.exceptions import ImproperlyConfigured

from config.env import env, env_bool, env_int, env_list

NAME = "TERNA_TEST_SETTING"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv(NAME, raising=False)
    monkeypatch.delenv(f"{NAME}_FILE", raising=False)


@pytest.fixture
def secret_file(tmp_path):
    path = tmp_path / "secret"
    path.write_text("from-file\n", encoding="utf-8")
    return path


def test_reads_value_from_file_and_strips_newline(monkeypatch, secret_file):
    monkeypatch.setenv(f"{NAME}_FILE", str(secret_file))
    assert env(NAME) == "from-file"


def test_direct_value_wins_over_file(monkeypatch, secret_file):
    monkeypatch.setenv(NAME, "direct")
    monkeypatch.setenv(f"{NAME}_FILE", str(secret_file))
    assert env(NAME) == "direct"


def test_empty_direct_value_falls_back_to_file(monkeypatch, secret_file):
    # Compose passes unset overrides as empty strings.
    monkeypatch.setenv(NAME, "")
    monkeypatch.setenv(f"{NAME}_FILE", str(secret_file))
    assert env(NAME) == "from-file"


def test_missing_required_value_fails_fast():
    with pytest.raises(ImproperlyConfigured, match=NAME):
        env(NAME)


def test_unreadable_file_fails_fast(monkeypatch, tmp_path):
    monkeypatch.setenv(f"{NAME}_FILE", str(tmp_path / "missing"))
    with pytest.raises(ImproperlyConfigured, match="Cannot read"):
        env(NAME)


def test_default_applies_when_unset():
    assert env(NAME, "fallback") == "fallback"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), ("1", True), ("YES", True), ("on", True), ("false", False), ("0", False)],
)
def test_env_bool(monkeypatch, raw, expected):
    monkeypatch.setenv(NAME, raw)
    assert env_bool(NAME, default=not expected) is expected


def test_env_bool_default_when_unset():
    assert env_bool(NAME, default=True) is True


def test_env_int(monkeypatch):
    monkeypatch.setenv(NAME, "42")
    assert env_int(NAME, 0) == 42
    assert env_int("TERNA_TEST_UNSET_INT", 7) == 7


def test_env_list_drops_blanks(monkeypatch):
    monkeypatch.setenv(NAME, " localhost, ,127.0.0.1 ,")
    assert env_list(NAME, "") == ["localhost", "127.0.0.1"]
