#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты сервисов
"""

from src.services.database_service import DatabaseService
from src.services.auth_service import AuthService


class TestServices:
    """Тесты сервисов"""

    def test_database_singleton_does_not_open_a_connection(self, monkeypatch):
        class FakePool:
            closed = False

            def closeall(self):
                self.closed = True

        pools = []

        def initialize_without_connection(service):
            pool = FakePool()
            pools.append(pool)
            service._connection_pool = pool

        monkeypatch.setattr(
            DatabaseService, "_initialize_pool", initialize_without_connection
        )
        db1 = DatabaseService()
        db2 = DatabaseService()
        assert db1 is db2
        DatabaseService.reset_for_tests()
        assert pools[0].closed

    def test_auth_service_init(self, fake_database):
        auth = AuthService(fake_database)
        assert auth.db is fake_database

    def test_password_hash_different(self, auth_service):
        """Разные хеши для одинаковых паролей"""
        password = "Test123!"  # ✅ Короткий пароль
        hash1 = auth_service.get_password_hash(password)
        hash2 = auth_service.get_password_hash(password)
        assert hash1 != hash2  # Соль разная
        assert auth_service.verify_password(password, hash1)
        assert auth_service.verify_password(password, hash2)
        assert auth_service.verify_password(password, hash2)