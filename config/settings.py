#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Настройки приложения
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

project_root = Path(__file__).parent.parent

# Загрузка переменных окружения.
# Основной профиль — .env. Второй профиль можно выбрать запуском:
#   set DB_PROFILE=testdb
#   python main.py
database_profile = os.getenv("DB_PROFILE", "").strip().lower()
env_file = (
    project_root / f".env.{database_profile}"
    if database_profile
    else project_root / ".env"
)
load_dotenv(env_file, override=True)


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "SchoolTest"
    DB_USER: str = "school_psych_app"
    DB_PASSWORD: str = ""
    DB_SCHEMA: str = "psychology"
    
    # Security
    SECRET_KEY: str = "default-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Encryption
    ENCRYPTION_KEY: str = ""
    
    # Application
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
    
    @property
    def project_root(self) -> Path:
        return Path(__file__).parent.parent
    
    # ✅ Pydantic V2 ConfigDict
    model_config = SettingsConfigDict(
        env_file=str(env_file),
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Глобальный экземпляр
settings = Settings()