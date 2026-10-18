#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фикстуры для pytest
"""

import pytest
import sys
from pathlib import Path

# Импорт сервисов
from src.services.database_service import DatabaseService
from src.services.auth_service import AuthService

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def reset_database_service():
    """Автоматический сброс БД сервиса между тестами"""
    yield
    DatabaseService.reset_for_tests()


@pytest.fixture
def db_service():
    """Фикстура сервиса БД"""
    db = DatabaseService(for_tests=True)
    yield db
    # ✅ НЕ закрываем пул между тестами


@pytest.fixture
def auth_service(db_service):
    """Фикстура сервиса аутентификации"""
    return AuthService(db_service)


@pytest.fixture
def test_user():
    """Тестовые данные пользователя"""
    return {
        'login': 'test_admin',
        'password': 'Test123!',
        'email': 'test@school.local',
        'role': 'admin'
    }