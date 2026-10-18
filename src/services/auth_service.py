#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
School Psychology Testing App - Authentication Service
============================================================
Компонент: Сервис проверки безопасности и входа (Senior Level)
Функционал: Bcrypt хеширование, JWT-токены, Ролевая модель.
============================================================
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from config.settings import settings
from src.services.database_service import DatabaseService

# Инициализация логгера
logger = logging.getLogger(__name__)


class AuthService:
    """Сервис управления сеансами и безопасностью доступа."""

    def __init__(self, db_service: DatabaseService):
        """Инициализация через Dependency Injection."""
        self.db = db_service

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Сверка пароля в кодировке UTF-8 с хешем базы данных."""
        # 🚩 Ленивый импорт: bcrypt подгрузится только при вызове
        import bcrypt
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Security: Критическая ошибка верификации пароля: {e}")
            return False

    def get_password_hash(self, password: str) -> str:
        """Создание криптостойкого хеша по алгоритму Bcrypt."""
        import bcrypt
        # Стандарт bcrypt ограничивает длину пароля 72 байтами
        password_bytes = password.encode('utf-8')[:72]
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Генерация JWT токена для сессии."""
        from jose import jwt
        to_encode = data.copy()
        
        # Установка срока жизни токена (по умолчанию 60 минут)
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=60))
        to_encode.update({"exp": expire})
        
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Расшифровка и валидация входящего токена доступа."""
        from jose import JWTError, jwt
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"Auth: Попытка входа с невалидным токеном: {e}")
            return None

    def authenticate_user(self, login: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Проверка пользователя в БД и сбор метаданных.
        ✅ Возвращает student_id для правильной загрузки личного кабинета ученика.
        """
        try:
            with self.db.get_cursor() as cursor:
                # ВАЖНО: Четкий порядок колонок исключает ошибки индексов
                query = """
                    SELECT 
                        id,             -- [0] UUID пользователя
                        login,          -- [1] Логин (Код для ученика)
                        email,          -- [2]
                        password_hash,  -- [3]
                        role,           -- [4] admin/psychologist/student
                        student_id,     -- [5] ✅ Критично для кабинета ученика
                        school_id,      -- [6]
                        is_active,      -- [7]
                        is_verified     -- [8]
                    FROM psychology.users
                    WHERE login = %s
                """
                cursor.execute(query, (login,))
                user_row = cursor.fetchone()

                if not user_row:
                    logger.warning(f"Auth: Попытка входа с несуществующим логином: {login}")
                    return None

                # 1. Проверка пароля (используем хеш из базы)
                if not self.verify_password(password, user_row[3]):
                    logger.warning(f"Auth: Неверный пароль для пользователя {login}")
                    return None

                # 2. Проверка состояния аккаунта (is_active)
                if not user_row[7]:  
                    logger.warning(f"Auth: Попытка входа в заблокированный аккаунт: {login}")
                    return None

                logger.info(f"✅ Успешная аутентификация: {login} (роль: {user_row[4]})")

                # Формируем итоговый словарь для GUI
                return {
                    'id': str(user_row[0]),
                    'login': user_row[1],
                    'email': user_row[2],
                    'role': user_row[4],
                    'student_id': str(user_row[5]) if user_row[5] else None, # ID из базы учеников
                    'school_id': str(user_row[6]) if user_row[6] else None,
                    'is_verified': user_row[8]
                }

        except Exception as e:
            logger.error(f"Auth: Системная ошибка службы аутентификации: {e}")
            import traceback
            traceback.print_exc()
            return None