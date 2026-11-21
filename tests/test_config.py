#tets/test_config.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты конфигурации приложения
"""


from config.settings import Settings


class TestSettings:
    """Configuration tests independent of developer-specific .env values."""

    def test_settings_accept_database_configuration(self):
        settings = Settings(
            DB_HOST="127.0.0.1",
            DB_PORT=5432,
            DB_NAME="school_test",
            DB_USER="app_user",
            DB_PASSWORD="test_password",
            DB_SCHEMA="psychology",
        )

        assert settings.DB_HOST == "127.0.0.1"
        assert settings.DB_PORT == 5432
        assert settings.DB_NAME == "school_test"
        assert settings.DB_USER == "app_user"
        assert settings.DB_SCHEMA == "psychology"

    def test_database_url_uses_configured_values(self):
        settings = Settings(
            DB_HOST="db.example.test",
            DB_PORT=5544,
            DB_NAME="school_test",
            DB_USER="app_user",
            DB_PASSWORD="test_password",
        )

        assert settings.database_url == (
            "postgresql://app_user:test_password@db.example.test:5544/school_test"
        )

    def test_security_and_token_settings_are_configurable(self):
        settings = Settings(
            SECRET_KEY="unit-test-key-that-is-not-a-production-secret",
            ALGORITHM="HS256",
            ACCESS_TOKEN_EXPIRE_MINUTES=15,
        )

        assert settings.SECRET_KEY.startswith("unit-test-")
        assert settings.ALGORITHM == "HS256"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15