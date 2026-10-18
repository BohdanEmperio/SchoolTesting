#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты сервисов
"""

from src.services.database_service import DatabaseService
from src.services.auth_service import AuthService


class TestServices:
    """Тесты сервисов"""
    
    def test_database_singleton(self):
        """Проверка одиночки БД"""
        db1 = DatabaseService()
        db2 = DatabaseService()
        assert db1 is db2
    
    def test_auth_service_init(self, db_service):
        """Инициализация сервиса аутентификации"""
        auth = AuthService(db_service)
        assert auth.db is db_service
    
    def test_password_hash_different(self, auth_service):
        """Разные хеши для одинаковых паролей"""
        password = "Test123!"  # ✅ Короткий пароль
        hash1 = auth_service.get_password_hash(password)
        hash2 = auth_service.get_password_hash(password)
        assert hash1 != hash2  # Соль разная
        assert auth_service.verify_password(password, hash1)
        assert auth_service.verify_password(password, hash2)
        assert auth_service.verify_password(password, hash2)