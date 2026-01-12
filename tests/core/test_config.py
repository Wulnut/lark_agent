import os
import pytest
from src.core.config import Settings


def test_settings_load_from_env(monkeypatch):
    """Test that settings load correctly from environment variables."""
    monkeypatch.setenv("LARK_APP_ID", "cli_test_123")
    monkeypatch.setenv("LARK_APP_SECRET", "sec_test_456")
    monkeypatch.setenv("FEISHU_PROJECT_USER_TOKEN", "pt-token-val")
    monkeypatch.setenv("FEISHU_PROJECT_USER_KEY", "uk-key-val")

    # We pass _env_file=None to ignore the .env file and rely on monkeypatch
    settings = Settings(_env_file=None)

    assert settings.LARK_APP_ID == "cli_test_123"
    assert settings.LARK_APP_SECRET == "sec_test_456"
    assert settings.FEISHU_PROJECT_USER_TOKEN == "pt-token-val"
    assert settings.FEISHU_PROJECT_USER_KEY == "uk-key-val"


def test_settings_defaults():
    """Test default values for optional settings."""
    # Ensure mandatory fields are present to avoid validation error
    env = {"LARK_APP_ID": "dummy", "LARK_APP_SECRET": "dummy"}
    settings = Settings(_env_file=None, **env)
    assert settings.LARK_ENCRYPT_KEY is None
