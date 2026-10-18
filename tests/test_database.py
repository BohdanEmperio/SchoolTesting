#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты подключения к базе данных
"""

# ❌ УДАЛИТЬ: import pytest
# ❌ УДАЛИТЬ: from src.services.database_service import DatabaseService

from config.settings import settings


class TestDatabase:
    """Тесты базы данных"""
    
    def test_connection(self, db_service):
        """Проверка подключения к БД"""
        with db_service.get_cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
    
    def test_schema_exists(self, db_service):
        """Проверка существования схемы"""
        with db_service.get_cursor() as cursor:
            cursor.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name = %s
            """, (settings.DB_SCHEMA,))
            result = cursor.fetchone()
            assert result is not None
    
    def test_tables_count(self, db_service):
        """Проверка количества таблиц"""
        with db_service.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = %s
            """, (settings.DB_SCHEMA,))
            count = cursor.fetchone()[0]
            assert count >= 15  # Минимум 15 таблиц
    
    def test_users_table(self, db_service):
        """Проверка таблицы пользователей"""
        with db_service.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM psychology.users
            """)
            count = cursor.fetchone()[0]
            assert count >= 1  # Хотя бы админ