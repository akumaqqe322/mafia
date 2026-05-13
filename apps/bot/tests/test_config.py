import pytest
from app.core.config import get_settings

def test_settings_load():
    # It should load without error even if .env is missing (using defaults or env vars)
    settings = get_settings()
    assert settings.ENVIRONMENT in ["production", "development", "test"]

def test_settings_lru_cache():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
