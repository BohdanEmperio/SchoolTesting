#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
School Psychology Testing App - Authentication Service
============================================================
Компонент: Сервис проверки безопасности и входа.
Функционал: Bcrypt хеширование, JWT-токены, ролевая модель,
            создание учётных записей сотрудников.

ЭТАП 1 (14.11.2026): все правила «кто может создать учётную запись»
собраны здесь, в одном месте. Окна (экран входа, панель администратора)
только вызывают register_staff() и не могут обойти проверки.
============================================================
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from config.settings import settings
from src.services.database_service import DatabaseService

# Инициализация логгера
logger = logging.getLogger(__name__)

# Роли, которые можно выдать сотруднику. Роль 'student' сюда намеренно
# не входит: учётные записи учеников создаются только из вкладки «Ученики».
STAFF_ROLES = ("admin", "psychologist")

# Ключ для pg_advisory_xact_lock (произвольное число). Блокировка нужна,
# чтобы два одновременных «первых запуска» не создали двух администраторов.
_FIRST_ADMIN_LOCK_KEY = 2026111401


class RegistrationError(Exception):
    """Ошибка регистрации с понятным пользователю текстом (показывается в окне)."""


class AuthService:
    """Сервис управления сеансами и безопасностью доступа."""

    def __init__(self, db_service: DatabaseService):
        """Инициализация через Dependency Injection."""
        self.db = db_service

    # ------------------------------------------------------------------
    # Пароли и токены (без изменений)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Вход (без изменений)
    # ------------------------------------------------------------------

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
                    'student_id': str(user_row[5]) if user_row[5] else None,  # ID из базы учеников
                    'school_id': str(user_row[6]) if user_row[6] else None,
                    'is_verified': user_row[8]
                }

        except Exception as e:
            logger.error(f"Auth: Системная ошибка службы аутентификации: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ------------------------------------------------------------------
    # ЭТАП 1. Создание учётных записей сотрудников
    # ------------------------------------------------------------------

    def has_active_admin(self) -> bool:
        """
        Есть ли в системе хотя бы один активный администратор.

        От ответа зависит, показывать ли на экране входа кнопку
        «Первичная настройка». Если база недоступна или запрос упал,
        возвращаем True («администратор есть») — то есть кнопку СКРЫВАЕМ.
        Принцип «при сомнении — запретить» (fail closed): лучше временно
        не дать создать первого админа, чем открыть регистрацию всем.
        """
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM psychology.users
                        WHERE role = 'admin'::psychology.user_role
                          AND is_active = TRUE
                    );
                    """
                )
                return bool(cursor.fetchone()[0])
        except Exception as e:
            logger.error(f"Auth: не удалось проверить наличие администратора: {e}")
            return True  # fail closed

    @staticmethod
    def validate_staff_input(
        login: str, email: Optional[str], password: str, confirm: str
    ) -> Optional[str]:
        """
        Проверка полей формы сотрудника. Возвращает текст ошибки или None.

        Метод статический: им пользуется и окно (чтобы сразу подсветить ошибку),
        и register_staff() (чтобы проверка не обходилась при вызове из кода).
        """
        if not re.fullmatch(r"[a-zA-Z0-9_]{3,30}", login or ""):
            return "Логин должен содержать от 3 до 30 символов (латиница, цифры, '_')"
        if email and not re.fullmatch(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", email):
            return "Неверный формат адреса электронной почты"
        if len(password or "") < 8:
            return "Пароль должен содержать не менее 8 символов"
        if password != confirm:
            return "Введенные пароли не совпадают"
        return None

    def register_staff(
        self,
        login: str,
        email: Optional[str],
        password: str,
        confirm: str,
        role: str,
        created_by: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Создаёт учётную запись сотрудника и возвращает её UUID.

        Правила доступа:
          1. Если активного администратора нет (первый запуск) — разрешено
             создать ТОЛЬКО администратора, кем бы ни был вызывающий.
          2. Если администратор есть — создавать сотрудников может только
             вошедший администратор (created_by['role'] == 'admin').
          3. Роль — только 'admin' или 'psychologist'.

        При нарушении правил выбрасывает RegistrationError с текстом для окна.
        """
        # --- Шаг 1. Проверка формата полей (до обращения к базе) ---
        error = self.validate_staff_input(login, email, password, confirm)
        if error:
            raise RegistrationError(error)
        if role not in STAFF_ROLES:
            raise RegistrationError("Недопустимая роль сотрудника.")

        caller_role = (created_by or {}).get("role")
        caller_login = (created_by or {}).get("login", "экран входа")

        with self.db.get_cursor() as cursor:
            # --- Шаг 2. Блокировка на время транзакции ---
            # pg_advisory_xact_lock заставляет одновременные регистрации
            # выполняться по очереди и сама снимается при COMMIT/ROLLBACK.
            # Без неё два компьютера при первом запуске могли бы одновременно
            # увидеть «админа нет» и оба создать администратора.
            cursor.execute("SELECT pg_advisory_xact_lock(%s);", (_FIRST_ADMIN_LOCK_KEY,))

            # --- Шаг 3. Есть ли уже активный администратор? ---
            # Проверяем ВНУТРИ той же транзакции, после блокировки,
            # а не берём старый ответ из окна: за время заполнения формы
            # другой человек мог успеть создать администратора.
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM psychology.users
                    WHERE role = 'admin'::psychology.user_role AND is_active = TRUE
                );
                """
            )
            admin_exists = bool(cursor.fetchone()[0])

            # --- Шаг 4. Правила доступа ---
            if not admin_exists:
                # Первый запуск: создать можно только администратора.
                if role != "admin":
                    raise RegistrationError(
                        "В системе ещё нет администратора. "
                        "Сначала создайте учётную запись администратора."
                    )
            elif caller_role != "admin":
                # Администратор уже есть, а вызывающий — не администратор
                # (экран входа без авторизации или психолог из панели).
                logger.warning(
                    f"Auth: отклонена попытка создать сотрудника '{login}' "
                    f"(роль {role}) пользователем без прав администратора: {caller_login}"
                )
                raise RegistrationError(
                    "Создавать учётные записи сотрудников может только администратор."
                )

            # --- Шаг 5. Уникальность логина и e-mail ---
            # Дают понятное сообщение. Последнюю защиту всё равно обеспечивают
            # UNIQUE-ограничения таблицы users.
            cursor.execute("SELECT 1 FROM psychology.users WHERE login = %s;", (login,))
            if cursor.fetchone():
                raise RegistrationError("Этот логин уже занят. Выберите другой.")
            if email:
                cursor.execute("SELECT 1 FROM psychology.users WHERE email = %s;", (email,))
                if cursor.fetchone():
                    raise RegistrationError("Пользователь с таким e-mail уже зарегистрирован.")

            # --- Шаг 6. Запись сотрудника ---
            # Пароль хранится только в виде bcrypt-хеша.
            # email = None (а не пустая строка), чтобы не нарушить UNIQUE.
            cursor.execute(
                """
                INSERT INTO psychology.users (
                    login, email, password_hash, role,
                    school_id, student_id, is_active, is_verified
                )
                VALUES (%s, %s, %s, %s::psychology.user_role, %s, NULL, TRUE, TRUE)
                RETURNING id;
                """,
                (
                    login,
                    email or None,
                    self.get_password_hash(password),
                    role,
                    DatabaseService.DEFAULT_SCHOOL_ID,
                ),
            )
            new_id = str(cursor.fetchone()[0])

        # Сюда попадаем только после успешного COMMIT (выход из with без ошибки).
        logger.info(
            f"✅ Создан сотрудник: {login} (роль: {role}); создал: {caller_login}"
            + ("" if admin_exists else " [первичная настройка]")
        )
        return new_id
