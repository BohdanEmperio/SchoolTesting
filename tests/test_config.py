#tets/test_config.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты конфигурации приложения
"""


from config.settings import settings


class TestSettings:
    """Тесты настроек"""
    
    def test_db_host(self):
        """Проверка хоста БД"""
        assert settings.DB_HOST in ['localhost', '127.0.0.1']
    
    def test_db_port(self):
        """Проверка порта БД"""
        assert settings.DB_PORT == 5432
    
    def test_db_name(self):
        """Проверка имени БД для проекта"""
        assert settings.DB_NAME in ['SchoolTest', 'school_psychology_db']
    
    def test_db_user(self):
        """Проверка пользователя БД"""
        # ✅ ИСПРАВЛЕНО: school_psych_app (из дампа Scoopoi.backup.pdf)
        assert settings.DB_USER == 'school_psych_app'
    
    def test_db_schema(self):
        """Проверка схемы БД"""
        assert settings.DB_SCHEMA == 'psychology'
    
    def test_secret_key_exists(self):
        """Проверка секретного ключа"""
        assert len(settings.SECRET_KEY) >= 32
    
    def test_algorithm(self):
        """Проверка алгоритма"""
        assert settings.ALGORITHM == 'HS256'
    
    def test_database_url(self):
        """Проверка URL БД"""
        url = settings.database_url
        assert 'postgresql://' in url
        assert settings.DB_NAME in url