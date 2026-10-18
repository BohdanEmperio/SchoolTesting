#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты моделей данных
"""

import uuid
from datetime import datetime

from src.models.student import Student
from src.models.user import User


class TestModels:
    """Тесты моделей"""
    
    def test_user_creation(self):
        """Создание пользователя"""
        user = User(
            id=uuid.uuid4(),
            login="test_user",
            email="test@school.local",
            role="admin",
            school_id=None
        )
        assert user.login == "test_user"
        assert user.role == "admin"
        # ✅ ИСПРАВЛЕНО: Прямая проверка булева значения
        assert user.is_active
    
    def test_student_creation(self):
        """Создание ученика"""
        student = Student(
            id=uuid.uuid4(),
            student_code="STU001",
            first_name_enc=b'test',
            last_name_enc=b'test',
            middle_name_enc=None,
            birth_date=None,
            gender=None,
            class_id=None
        )
        assert student.student_code == "STU001"
        # ✅ ИСПРАВЛЕНО: Прямая проверка булева значения
        assert student.is_active
    
    def test_user_from_db(self):
        """Создание пользователя из БД"""
        row = (
            uuid.uuid4(),
            "db_user",
            "db@school.local",
            "psychologist",
            uuid.uuid4(),
            True,
            True,
            datetime.now()
        )
        user = User.from_db(row)
        assert user.login == "db_user"
        assert user.role == "psychologist"
        