#!/usr/bin/env python3
# -*- coding: utf-8 -*-\
#src/service/database_service.py
"""
================================================================================
School Psychology Testing App - Database Service (Ultra Master V9.0)
================================================================================
Backend-инфраструктура взаимодействия с PostgreSQL.
--------------------------------------------------------------------------------
ФУНКЦИОНАЛЬНЫЕ СЕКЦИИ:
1. Контроль соединений (Пул Singleton)
2. Учебные группы (Классы)
3. Картотека учащихся (BYTEA-шифрование ФИО)
4. Служба доступа (Аккаунты и ключи входа)
5. Библиотека тестов (CRUD + Структура + Сложное сохранение)
6. Психометрический движок (Математический расчет по шкалам)
7. Интеллектуальный AI PDF Parser (Regex + Table Mapping)
8. Модули отчетности и Протоколы результатов
================================================================================
"""

import json
import logging
import re
import secrets
import traceback
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple

import pdfplumber
from psycopg2 import pool

from config.settings import settings

# Настройка глобального регистратора системных событий
logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Индустриальный Singleton-сервис для работы с СУБД.
    Внедрена защита от утечек памяти и автоматизация SQL-транзакций.
    """

    _instance: Optional['DatabaseService'] = None
    _connection_pool: Optional[pool.SimpleConnectionPool] = None
    _for_tests: bool = False

    # Системные константы школы (Иркутская обл., г. Братск, СОШ №18)
    DEFAULT_SCHOOL_ID = "00000000-0000-0000-0000-000000000001"
    DEFAULT_YEAR_ID = "00000000-0000-0000-0000-000000000001"

    # ============================================================
    # 🧩 СИСТЕМНЫЕ МЕТОДЫ ИНИЦИАЛИЗАЦИИ (SINGLETON PATTERN)
    # ============================================================

    def __new__(cls, for_tests: bool = False):
        """
        Механика паттерна Singleton (Одиночка).
        Предотвращает создание конкурирующих соединений и переполнение 
        пула ресурсов PostgreSQL при многократных вызовах DatabaseService().
        
        :param for_tests: Если True, возвращает изолированный объект вне синглтона.
        """
        if for_tests:
            # Специфический сценарий: создание уникального экземпляра для модульного тестирования
            # Чтобы тесты не влияли на состояние основной базы данных приложения
            instance = super().__new__(cls)
            instance._for_tests = True
            # Сбрасываем пул для тестового объекта, чтобы он создал свой собственный
            instance._connection_pool = None
            return instance
        
        # Основной сценарий: возврат существующего или создание единственного экземпляра
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Флаг тестов для основного синглтона всегда False
            cls._instance._for_tests = False
            
        return cls._instance

    def __init__(self, for_tests: bool = False):
        """
        Инициализация ресурсов при обращении к сервису.
        
        Примечание: В Python __init__ вызывается каждый раз при вызове класса.
        Проверка 'if self._connection_pool is None' критически важна, чтобы 
        не перезапускать пул соединений при получении существующего объекта.
        """
        if self._connection_pool is None:
            # Если пул еще не создан (первый запуск программы), инициализируем его
            # Метод _initialize_pool выполнит реальное подключение к PostgreSQL
            self._initialize_pool()
        else:
            # Этот лог поможет в дебаге понять, что Singleton работает исправно
            logger.debug("DatabaseService: Пул уже активен, повторная инициализация пропущена.")

    def ping(self) -> bool:
        """Проверка корректности подключения к PostgreSQL без полной инициализации бизнес-логики."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                return result is not None and result[0] == 1
        except Exception as exc:
            logger.error(f"DatabaseService: Проверка подключения не удалась: {exc}")
            return False
            
            

    def _initialize_pool(self):
        """
        📐 Универсальная инициализация пула, устойчивая к кириллице в путях Windows.
        Исправлено: временная очистка PATH для предотвращения UnicodeDecodeError.
        """
        from psycopg2.pool import ThreadedConnectionPool
        import os
        import sys

        # Сохраняем оригинальный PATH, чтобы восстановить его позже
        original_path = os.environ.get('PATH', '')

        # ШАГ 1: Изоляция от системных путей Windows.
        os.environ['PGPASSFILE'] = os.devnull
        os.environ['PGSERVICEFILE'] = os.devnull
        os.environ['PGCLIENTENCODING'] = 'utf-8'
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: 
        # Временно очищаем PATH, оставляя только системные папки Windows.
        # Это не даст psycopg2 споткнуться о папку "Богдан" при инициализации.
        if sys.platform == 'win32':
            os.environ['PATH'] = "C:\\Windows\\system32;C:\\Windows"

        logger.debug(f"Инициализация подключения к БД: {settings.DB_HOST}:{settings.DB_PORT}")

        try:
            # ШАГ 2: Формируем параметры словарем (надежнее для драйвера)
            db_params = {
                'host': str(settings.DB_HOST).strip(),
                'port': int(settings.DB_PORT),  # <--- УБРАЛИ .strip() ЗДЕСЬ
                'database': str(settings.DB_NAME).strip(),
                'user': str(settings.DB_USER).strip(),
                'password': str(settings.DB_PASSWORD).strip(),
                'options': f"-c search_path={str(settings.DB_SCHEMA).strip()} -c timezone=Asia/Irkutsk",
                'connect_timeout': 10,
                'client_encoding': 'UTF8'
            }

            # ШАГ 3: Инициализация пула
            self._connection_pool = ThreadedConnectionPool(
                minconn=5,
                maxconn=35,
                **db_params
            )
            
            logger.info(
                f"✅ DatabaseService: Пул развернут успешно. "
                f"Целевая схема: '{settings.DB_SCHEMA}'."
            )

        except Exception as error:
            detailed_err = f"Критический сбой инициализации пула данных: {error}"
            logger.critical(f"❌ {detailed_err}")
            raise error
        
        finally:
            # ОБЯЗАТЕЛЬНО восстанавливаем PATH, чтобы другие части программы 
            # (например, вызов браузера или работа с PDF) не сломались.
            os.environ['PATH'] = original_path

    @contextmanager
    def get_connection(self) -> Generator:
        """
        🚀 Высокоуровневый контекстный менеджер для безопасной аренды сессии из пула.
        
        Обеспечивает:
        1. Проверку готовности инфраструктуры БД перед началом работы.
        2. Атомарное получение свободного сокета.
        3. Гарантированный возврат (RELEASE) коннекта в пул через блок finally.
        4. Предотвращение 'утечек соединений', которые приводят к зависанию Postgres.
        
        :return: Generator, выдающий объект соединения psycopg2.connection
        :raises RuntimeError: Если пул соединений не был проинициализирован.
        :raises Exception: Если не удалось арендовать коннект (например, достигнут лимит maxconn).
        """
        # Валидация состояния объекта DatabaseService
        if self._connection_pool is None:
            err_msg = "🚨 Критический сбой логики: Попытка выполнения SQL-запроса до запуска пула соединений."
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        # Переменная для хранения ссылки на арендованный ресурс
        active_connection = None

        try:
            # Арендуем коннект из ThreadedConnectionPool
            # Если все соединения заняты, поток будет ожидать освобождения (блокирующая операция)
            active_connection = self._connection_pool.getconn()
            
            # На всякий случай проверяем состояние сокета (мгновенный ping базы)
            # Это исключает ошибки 'connection already closed', если Postgres упал и поднялся
            if active_connection.closed:
                logger.warning("⚠️ Получено закрытое соединение из пула. Пытаемся восстановить...")
            
            # Передаем соединение во внешний код (в блок 'with' вызывающего метода)
            yield active_connection

        except Exception as rental_err:
            logger.error(f"❌ Ошибка в момент удержания соединения: {rental_err}")
            # Мы не обрабатываем ошибку здесь, а передаем её выше (в get_cursor или логику GUI)
            raise rental_err

        finally:
            # ❗ КРИТИЧЕСКИ ВАЖНЫЙ ЭТАП:
            # Даже если внутри блока 'with' произошел краш, база ОБЯЗАНА получить коннект обратно.
            # Иначе за 35-50 нажатий кнопок база данных исчерпает лимиты и 'умрет'.
            if active_connection:
                try:
                    self._connection_pool.putconn(active_connection)
                    logger.debug("📡 Соединение успешно возвращено в пул ресурсов.")
                except Exception as put_err:
                    # Это случается крайне редко (если пул был закрыт из другого потока)
                    logger.error(f"⚠️ Не удалось корректно вернуть коннект в пул: {put_err}")
                    

    @contextmanager
    def get_cursor(self):
        """
        💎 Мастер-метод управления транзакциями (Transactional Facade).
        
        Реализует паттерн Unit of Work:
        1. Арендует соединение из пула.
        2. Открывает изолированный курсор для выполнения SQL.
        3. Выполняет автоматический COMMIT, если блок 'with' завершился успешно.
        4. Производит экстренный ROLLBACK в случае любого исключения.
        5. Гарантированно освобождает ресурсы (закрытие курсора).
        
        Позволяет писать чистый код без постоянных commit/rollback в бизнес-логике.
        """
        # Арендуем соединение через ранее созданный контекстный менеджер
        with self.get_connection() as active_connection:
            # Инициализация курсора
            # Используем стандартный курсор для повышения производительности (выборка в виде Tuple)
            sql_cursor = active_connection.cursor()
            
            try:
                # Передаем управление в блок 'with', где будет реальный SQL-запрос
                yield sql_cursor
                
                # Если выполнение в вызывающем коде прошло успешно (не вылетело Exception),
                # фиксируем все изменения в базе данных физически.
                active_connection.commit()
                logger.debug("✅ SQL Транзакция успешно зафиксирована (Committed).")
                
            except Exception as transaction_fail:
                # В случае любой ошибки (программной или серверной) — 
                # ОБЯЗАТЕЛЬНО отменяем все изменения в рамках этого курсора.
                # Это предотвращает попадание в базу 'сломанных' или неполных данных.
                active_connection.rollback()
                
                # Собираем детализированный отчет об ошибке для лога
                error_type = type(transaction_fail).__name__
                logger.error(f"⚠️ БД КРИТИЧЕСКИЙ СБОЙ: [{error_type}] -> {transaction_fail}")
                
                # Выводим полный Traceback для отладки сложной логики (например, ошибки в триггерах)
                # Убедитесь, что 'import traceback' есть в начале файла
                traceback.print_exc()
                
                # Пробрасываем ошибку выше, чтобы UI мог показать уведомление пользователю
                raise transaction_fail
                
            finally:
                # В конце жизненного цикла курсора освобождаем ресурсы PostgreSQL
                # (Курсор закрывается всегда, независимо от успеха транзакции)
                sql_cursor.close()
                logger.debug("🧹 Курсор освобожден и закрыт.")

    # ==========================================================================
    # 📚 [БЛОК 1] : УПРАВЛЕНИЕ УЧЕБНЫМИ ГРУППАМИ (КЛАССАМИ)
    # ==========================================================================

    def get_all_classes(self) -> List[Tuple]:
        """Загрузка каталога классов с подзапросом на реальный расчет людей."""
        query = """
            SELECT 
                c.id, 
                c.class_name, 
                c.grade_level, 
                (SELECT COUNT(*) FROM psychology.students s 
                 WHERE s.class_id = c.id AND s.is_active = TRUE) as actual_students
            FROM psychology.classes c 
            WHERE c.is_active = TRUE 
            ORDER BY c.grade_level ASC, c.class_name ASC;
        """
        with self.get_cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()

    def add_class(self, title: str, parallel: int, letter: str) -> str:
        """Добавление новой записи в структуру школы."""
        sql_command = """
            INSERT INTO psychology.classes 
            (school_id, academic_year_id, class_name, grade_level, letter, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING id;
        """
        data_values = (self.DEFAULT_SCHOOL_ID, self.DEFAULT_YEAR_ID, title, parallel, letter)
        with self.get_cursor() as cursor:
            cursor.execute(sql_command, data_values)
            return cursor.fetchone()[0]

    def update_class(self, cid: str, new_name: str):
        """Изменяет имя класса с коррекцией его уровня."""
        grade_parsed = int(''.join(filter(str.isdigit, new_name)) or 0)
        with self.get_cursor() as cur:
            cur.execute("UPDATE psychology.classes SET class_name=%s, grade_level=%s WHERE id=%s", 
                        (new_name, grade_parsed, cid))

    def delete_class(self, cid: str):
        """Мгновенное удаление класса по первичному ключу."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM psychology.classes WHERE id = %s", (cid,))
            logger.info(f"Справочник: Класс ID {cid} удален.")

   # ==========================================================================
    # 🎓 [БЛОК 2] : КАРТОТЕКА УЧАЩИХСЯ (ПОЛНАЯ СИНХРОНИЗАЦИЯ С БД)
    # ==========================================================================

    def get_students_by_class(self, class_filter_uuid: str = None) -> List[Tuple]:
        """
        Выборка учеников. Теперь возвращает ПОЛНЫЙ набор данных (12 колонок).
        Порядок: id, code, first_enc, last_enc, middle_enc, b_date, gender, class_name...
        """
        query_sql = """
            SELECT 
                s.id,               -- [0]
                s.student_code,      -- [1]
                s.first_name_enc,    -- [2]
                s.last_name_enc,     -- [3]
                s.middle_name_enc,    -- [4]
                s.birth_date,        -- [5] ✅ НОВОЕ
                s.gender,            -- [6] ✅ НОВОЕ
                c.class_name         -- [7]
            FROM psychology.students s 
            LEFT JOIN psychology.classes c ON s.class_id = c.id
            WHERE s.is_active = TRUE
        """
        args_val = []
        if class_filter_uuid:
            query_sql += " AND s.class_id = %s"
            args_val.append(class_filter_uuid)
        
        with self.get_cursor() as cursor:
            # Сортировка по фамилии в БД (байты тоже сортируются по алфавиту)
            cursor.execute(query_sql + " ORDER BY s.last_name_enc ASC", args_val)
            return cursor.fetchall()

    @staticmethod
    def _insert_student_record(
        cursor,
        s_code: str,
        f_name: str,
        l_name: str,
        m_name: str,
        birth_date: str,
        gender: str,
        c_id: str,
    ) -> str:
        """Insert an encrypted student profile inside the caller's transaction."""
        generated_salt = secrets.token_bytes(16)

        cursor.execute(
            """
                INSERT INTO psychology.students (
                    student_code, first_name_enc, last_name_enc, middle_name_enc,
                    encryption_salt, birth_date, gender, class_id, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING id;
            """,
            (
                str(s_code)[:100],
                f_name.encode("utf-8"),
                l_name.encode("utf-8"),
                m_name.encode("utf-8") if m_name else None,
                generated_salt,
                birth_date,
                gender,
                c_id,
            ),
        )
        return str(cursor.fetchone()[0])

    @staticmethod
    def _insert_student_consent(cursor, student_id: str) -> None:
        cursor.execute(
            """
                INSERT INTO psychology.data_processing_consent (
                    student_id, consent_given, consent_date, is_active
                )
                VALUES (%s, TRUE, CURRENT_TIMESTAMP, TRUE)
                ON CONFLICT (student_id) DO UPDATE
                SET consent_given = TRUE,
                    consent_date = CURRENT_TIMESTAMP,
                    is_active = TRUE,
                    updated_at = CURRENT_TIMESTAMP;
            """,
            (student_id,),
        )

    def add_student(
        self,
        s_code: str,
        f_name: str,
        l_name: str,
        m_name: str,
        birth_date: str,
        gender: str,
        c_id: str,
        consent_given: bool = False,
    ) -> str:
        """
        Регистрация анкеты с полной поддержкой метаданных (пол и дата рождения).
        :param birth_date: строка в формате ISO (YYYY-MM-DD) или None
        :param gender: 'Муж' или 'Жен'
        """
        with self.get_cursor() as cursor:
            student_id = self._insert_student_record(
                cursor, s_code, f_name, l_name, m_name, birth_date, gender, c_id
            )
            if consent_given:
                self._insert_student_consent(cursor, student_id)
            logger.info(f"✅ БД: Ученик {l_name} успешно зарегистрирован с метаданными.")
            return student_id

    def add_student_with_account(
        self,
        s_code: str,
        f_name: str,
        l_name: str,
        m_name: str,
        birth_date: str,
        gender: str,
        c_id: str,
        login: str,
        password_hash: str,
        consent_given: bool = False,
    ) -> str:
        """Create a student profile and login account atomically."""
        with self.get_cursor() as cursor:
            student_id = self._insert_student_record(
                cursor, s_code, f_name, l_name, m_name, birth_date, gender, c_id
            )
            cursor.execute(
                """
                    INSERT INTO psychology.users (
                        login, password_hash, role, student_id, is_active, is_verified
                    )
                    VALUES (%s, %s, 'student', %s, TRUE, TRUE);
                """,
                (login, password_hash, student_id),
            )
            if consent_given:
                self._insert_student_consent(cursor, student_id)
            logger.info(
                "✅ БД: Созданы профиль ученика %s и связанная учётная запись.",
                student_id,
            )
            return student_id

    def update_student(self, sid: str, f_n: str, l_n: str, m_n: str, 
                       birth_date: str, gender: str, c_id: str):
        """Обновление ФИО, пола и даты рождения."""
        m_bytes = m_n.encode('utf-8') if m_n else None
        
        update_query = """
            UPDATE psychology.students 
            SET first_name_enc=%s, last_name_enc=%s, middle_name_enc=%s, 
                birth_date=%s, gender=%s, class_id=%s, updated_at=CURRENT_TIMESTAMP 
            WHERE id=%s;
        """
        params = (f_n.encode('utf-8'), l_n.encode('utf-8'), m_bytes, birth_date, gender, c_id, sid)
        
        with self.get_cursor() as cur:
            cur.execute(update_query, params)
            logger.info(f"💾 БД: Данные ученика (ID: {sid}) обновлены.")

    def delete_student(self, stud_uuid: str):
        """Удаление ученика (используется ON DELETE CASCADE в зависимых таблицах)."""
        with self.get_cursor() as cur:
            cur.execute("DELETE FROM psychology.students WHERE id = %s;", (stud_uuid,))
            logger.warning(f"🚮 БД: Анкета {stud_uuid} полностью удалена из системы.")

    # ==========================================================================
    # 🔐 [БЛОК 3] : МОДУЛИ ДОСТУПА И БЕЗОПАСНОСТИ
    # ==========================================================================


    def get_student_consent(self, student_uuid: str) -> bool:
        """Проверка наличия подтвержденного согласия на обработку ПДн по 152-ФЗ."""
        query = """
            SELECT consent_given 
            FROM psychology.data_processing_consent 
            WHERE student_id = %s AND is_active = TRUE;
        """
        try:
            with self.get_cursor() as cur:
                cur.execute(query, (student_uuid,))
                row = cur.fetchone()
                return bool(row[0]) if row else False
        except Exception as e:
            logger.error(f"Ошибка проверки согласия ученика {student_uuid}: {e}")
            return False

    def set_student_consent(self, student_uuid: str, consent: bool = True):
        """Оформление / обновление согласия родителей на обработку ПДн."""
        sql = """
            INSERT INTO psychology.data_processing_consent (student_id, consent_given, consent_date, is_active)
            VALUES (%s, %s, CURRENT_TIMESTAMP, TRUE)
            ON CONFLICT (student_id) DO UPDATE 
            SET consent_given = EXCLUDED.consent_given,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP;
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (student_uuid, consent))
            logger.info(f"📋 БД: Согласие 152-ФЗ для ученика {student_uuid} установлено в {consent}")


    def create_student_account(self, student_uuid: str, login_str: str, hashed_pass: str):
        """Привязывает запись учащегося к системе входа в личный кабинет."""
        sql = """
            INSERT INTO psychology.users (login, password_hash, role, student_id, is_active, is_verified)
            VALUES (%s, %s, 'student', %s, TRUE, TRUE)
            ON CONFLICT (student_id) DO UPDATE SET 
            login=EXCLUDED.login, password_hash=EXCLUDED.password_hash, updated_at=CURRENT_TIMESTAMP;
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (login_str, hashed_pass, student_uuid))

    def revoke_student_access(self, student_uuid: str):
        """Мгновенное аннулирование доступа."""
        with self.get_cursor() as cur:
            cur.execute("UPDATE psychology.users SET is_active=FALSE WHERE student_id=%s", (student_uuid,))

    def get_student_profile(self, user_uuid: str) -> Optional[Tuple]:
        """Считывает зашифрованные поля имени через связь users->students."""
        query = """
            SELECT s.first_name_enc, s.last_name_enc, c.class_name
            FROM psychology.users u
            JOIN psychology.students s ON u.student_id = s.id
            JOIN psychology.classes c ON s.class_id = c.id
            WHERE u.id = %s;
        """
        with self.get_cursor() as cur:
            cur.execute(query, (user_uuid,))
            return cur.fetchone()

    # ==========================================================================
    # 📝 [БЛОК 4] : КОНСТРУКТОР ТЕСТОВ (БИБЛИОТЕКА)
    # ==========================================================================

    def get_all_tests(self) -> List[Tuple]:
        """Возвращает реестр тестов и динамический COUNT вопросов в каждом."""
        sql = """
            SELECT id, test_code, test_name, 
            (
                SELECT COUNT(*)
                FROM psychology.test_questions
                WHERE test_id = t.id AND is_active = TRUE
            )
            FROM psychology.psychological_tests t WHERE is_active=TRUE;
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()

    def add_test(
        self,
        code: str,
        name: str,
        desc: str,
        instructions: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Регистрация теста с расширенными полями."""
        query = """
            INSERT INTO psychology.psychological_tests (
                test_code, test_name, description, instructions, config, is_active
            )
            VALUES (%s, %s, %s, %s, %s::jsonb, TRUE)
            RETURNING id;
        """
        with self.get_cursor() as cur:
            cur.execute(
                query,
                (
                    code,
                    name,
                    desc,
                    instructions,
                    json.dumps(config or {}, ensure_ascii=False),
                ),
            )
            return str(cur.fetchone()[0])
        
    def update_test_metadata(
        self,
        test_id: str,
        code: str,
        name: str,
        desc: str,
        instr: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        🛡️ Обновление текстовых полей теста. 
        Исправлена ошибка адаптации UUID: передаем t_id как строку.
        """
      
        sql_query = """
            UPDATE psychology.psychological_tests 
            SET test_code = %s, 
                test_name = %s, 
                description = %s, 
                instructions = %s, 
                config = COALESCE(%s::jsonb, config),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """
        try:
            # Валидируем, что это корректный UUID
            target_uuid = uuid.UUID(str(test_id))
            
            with self.get_cursor() as cursor:
                # ✅ ИСПРАВЛЕНО: Превращаем объект UUID обратно в строку через str()
                cursor.execute(
                    sql_query,
                    (
                        code,
                        name,
                        desc,
                        instr,
                        json.dumps(config, ensure_ascii=False) if config is not None else None,
                        str(target_uuid),
                    ),
                )
                logger.info(f"Metadata Update: Данные теста {code} успешно обновлены.")
        except Exception as e:
            logger.error(f"Metadata Update Error: {e}")
            raise e

    
    def delete_test(self, test_id: str):
        """
        Archive a methodology without deleting its completed sessions or responses.
        """
        query = """
            UPDATE psychology.psychological_tests
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, (test_id,))
            cursor.execute(
                "UPDATE psychology.test_questions SET is_active = FALSE "
                "WHERE test_id = %s;",
                (test_id,),
            )
            cursor.execute(
                "UPDATE psychology.test_scales SET is_active = FALSE "
                "WHERE test_id = %s;",
                (test_id,),
            )
            logger.warning("Методика %s перемещена в архив.", test_id)

    def ensure_test_structure_editable(self, test_id: str) -> None:
        """Reject structural edits while a student is completing the methodology."""
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                    SELECT EXISTS (
                        SELECT 1
                        FROM psychology.test_sessions
                        WHERE test_id = %s::uuid AND status = 'in_progress'
                    );
                """,
                (str(uuid.UUID(str(test_id))),),
            )
            if cursor.fetchone()[0]:
                raise ValueError(
                    "Нельзя менять структуру методики, пока по ней есть "
                    "незавершенное тестирование."
                )

    def _get_question_media(
        self, cursor, question_ids: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Load image assets for a set of questions without exposing storage paths."""
        if not question_ids:
            return {}

        placeholders = ", ".join("%s::uuid" for _ in question_ids)
        cursor.execute(
            f"""
                SELECT question_id, media_key, media_role, option_id,
                       file_name, mime_type, file_data
                FROM psychology.test_question_media
                WHERE question_id = ANY(ARRAY[{placeholders}])
                ORDER BY created_at, id;
            """,
            tuple(question_ids),
        )

        media_by_question: Dict[str, List[Dict[str, Any]]] = {}
        for row in cursor.fetchall():
            media_by_question.setdefault(str(row[0]), []).append(
                {
                    "key": str(row[1]),
                    "role": str(row[2]),
                    "option_id": row[3],
                    "file_name": str(row[4]),
                    "mime_type": str(row[5]),
                    "data": bytes(row[6]),
                }
            )
        return media_by_question

    def get_test_full_structure(self, test_id: str) -> Tuple[List, List, Dict]:
        """
        🚀 Считывает ПОЛНУЮ архитектуру теста для отображения в инженерном редакторе.
        ВАЖНО: Порядок полей в SELECT шкал должен строго соответствовать методу add_s_row!
        """
        with self.get_cursor() as cur:
            # 1. Загрузка Свойств (Таблица psychological_tests)
            cur.execute("""
                SELECT test_code, test_name, description, instructions, config
                FROM psychology.psychological_tests 
                WHERE id = %s
            """, (test_id,))
            main_data = cur.fetchone()
            
            # Защита: если тест не найден в базе, возвращаем пустой "черновик"
            if not main_data:
                logger.warning(f"Metadata fail: Тест {test_id} не найден.")
                return [], [], {
                    "code": "",
                    "name": "Тест не найден",
                    "desc": "",
                    "instructions": "",
                    "test_mode": "yes_no",
                }

            # 2. Загрузка Листа Вопросов (Таблица test_questions)
            cur.execute("""
                SELECT id, question_text, options, order_index, question_type, media_content
                FROM psychology.test_questions 
                WHERE test_id = %s AND is_active = TRUE
                ORDER BY order_index ASC
            """, (test_id,))
            question_rows = cur.fetchall()
            media_by_question = self._get_question_media(
                cur, [str(row[0]) for row in question_rows]
            )
            questions = [
                {
                    "id": str(row[0]),
                    "text": str(row[1]),
                    "options": row[2],
                    "order": int(row[3]),
                    "question_type": str(row[4]),
                    "media_content": row[5] or {},
                    "media_assets": media_by_question.get(str(row[0]), []),
                }
                for row in question_rows
            ]
            
            # 3. Загрузка Правил Оценки (Таблица test_scales)
            # ✨ ИСПРАВЛЕНО: Добавлен coefficient в SELECT
            cur.execute("""
                SELECT 
                    scale_name,      -- [0] Фактор
                    scale_code,      -- [1] Маппинг №№ вопросов
                    min_score,       -- [2]
                    max_score,       -- [3]
                    interpretation,  -- [4] Текст заключения
                    coefficient      -- [5] КОЭФФИЦИЕНТ (Теперь подтянется из БД)
                FROM psychology.test_scales 
                WHERE test_id = %s AND is_active = TRUE
                ORDER BY scale_name ASC;
            """, (test_id,))
            scales = cur.fetchall()
            
            # Интеграция данных в словарь мета-информации (Tab 1)
            config = main_data[4] or {}
            if isinstance(config, str):
                config = json.loads(config)

            meta = {
                'code': str(main_data[0] or ''), 
                'name': str(main_data[1] or ''), 
                'desc': str(main_data[2] or ''), 
                'instructions': str(main_data[3] or ''),
                'test_mode': str(config.get("test_mode", "yes_no")),
            }
            
            logger.info(f"DB -> UI: Структура теста {meta['name']} выгружена (Вопр: {len(questions)}, шкал: {len(scales)})")
            return questions, scales, meta

    def save_test_structure(
        self,
        test_id: str,
        questions: List[Dict],
        scales: List[Dict],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        🚀 СИНХРОНИЗАЦИЯ СТРУКТУРЫ ТЕСТА И РАСЧЕТНЫХ ШКАЛ (V13.0).
        Сохраняет:
        1. Вопросы (test_questions).
        2. Шкалы (test_scales) с системными кодами SCALE_1..SCALE_9.
        3. Таблицу связей (question_scale_mapping) для процедуры calculate_osr_session.
        """
        logger.info(
            f"Начало обновления теста ID: {test_id}. "
            f"Вопросов: {len(questions)}, Шкал: {len(scales)}."
        )

        with self.get_connection() as connection:
            connection.autocommit = False
            cursor = connection.cursor()
            
            try:
                test_id_str = str(uuid.UUID(str(test_id)))
                cursor.execute(f"SET search_path TO {settings.DB_SCHEMA}, public;")

                cursor.execute(
                    """
                        SELECT EXISTS (
                            SELECT 1
                            FROM test_sessions
                            WHERE test_id = %s AND status = 'in_progress'
                        );
                    """,
                    (test_id_str,),
                )
                if cursor.fetchone()[0]:
                    raise ValueError(
                        "Нельзя менять структуру методики, пока по ней есть "
                        "незавершенное тестирование."
                    )

                if metadata is not None:
                    cursor.execute(
                        """
                            UPDATE psychological_tests
                            SET test_code = %s,
                                test_name = %s,
                                description = %s,
                                instructions = %s,
                                config = %s::jsonb,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s;
                        """,
                        (
                            metadata["code"],
                            metadata["name"],
                            metadata["description"],
                            metadata["instructions"],
                            json.dumps(metadata["config"], ensure_ascii=False),
                            test_id_str,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError(f"Методика {test_id_str} не найдена.")

                # Keep previous question and scale rows so completed sessions retain
                # their foreign-key targets and historical report data.
                cursor.execute(
                    "UPDATE test_questions SET is_active = FALSE "
                    "WHERE test_id = %s AND is_active = TRUE;",
                    (test_id_str,),
                )
                cursor.execute(
                    "UPDATE test_scales SET is_active = FALSE "
                    "WHERE test_id = %s AND is_active = TRUE;",
                    (test_id_str,),
                )

                # 2. Store the new active question structure.
                order_to_qid: Dict[int, str] = {}
                for q in questions:
                    opt_data = q['options']
                    if isinstance(opt_data, str):
                        opt_data = json.loads(opt_data)
                    media_content = q.get("media_content", {})
                    if isinstance(media_content, str):
                        media_content = json.loads(media_content)

                    cursor.execute("""
                        INSERT INTO test_questions 
                        (
                            test_id, question_text, question_type, order_index,
                            options, media_content, is_active
                        )
                        VALUES (%s, %s, %s::psychology.question_type_enum,
                                %s, %s::jsonb, %s::jsonb, TRUE)
                        RETURNING id, order_index;
                    """, (
                        test_id_str,
                        q['text'],
                        q.get("question_type", "single_choice"),
                        int(q['order']),
                        json.dumps(opt_data, ensure_ascii=False),
                        json.dumps(media_content, ensure_ascii=False),
                    ))
                    
                    row = cursor.fetchone()
                    if row:
                        order_to_qid[int(row[1])] = str(row[0])

                        for asset in q.get("media_assets", []):
                            cursor.execute(
                                """
                                    INSERT INTO test_question_media (
                                        question_id, media_key, media_role, option_id,
                                        file_name, mime_type, file_data
                                    )
                                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                                """,
                                (
                                    str(row[0]),
                                    str(asset["key"]),
                                    str(asset["role"]),
                                    asset.get("option_id"),
                                    str(asset["file_name"]),
                                    str(asset["mime_type"]),
                                    bytes(asset["data"]),
                                ),
                            )

                # 3. Store active scales and their mappings.
                for idx, s in enumerate(scales):
                    # Извлекаем номер шкалы из названия (например: '1. Демонстративность' -> 1)
                    scale_num_match = re.search(r'^\s*(\d+)', str(s['name']))
                    scale_num = int(scale_num_match.group(1)) if scale_num_match else (idx + 1)
                    scale_code = f"SCALE_{scale_num}"

                    raw_mapping = str(s.get('mapping', '')).replace(' ', '')

                    cursor.execute("""
                        INSERT INTO test_scales 
                        (
                            test_id, scale_name, scale_code, min_score, max_score,
                            interpretation, coefficient, is_active
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                        RETURNING id;
                    """, (
                        test_id_str,
                        s['name'], 
                        scale_code,
                        int(s.get('min', 0)), 
                        float(s['max']), 
                        s['interpretation'], 
                        float(s.get('coef', 1.0))
                    ))
                    
                    scale_id = str(cursor.fetchone()[0])

                    # 4. Map question numbers to this active scale.
                    q_indices = [int(x.strip()) for x in raw_mapping.split(',') if x.strip().isdigit()]
                    for q_order in q_indices:
                        qid = order_to_qid.get(q_order)
                        if qid:
                            cursor.execute("""
                                INSERT INTO question_scale_mapping (question_id, scale_id, weight)
                                VALUES (%s, %s, 1.0)
                                ON CONFLICT (question_id, scale_id) DO NOTHING;
                            """, (qid, scale_id))

                connection.commit()
                logger.info(f"💎 УСПЕХ: Структура теста {test_id} и question_scale_mapping успешно сохранены в БД.")

            except Exception as e:
                connection.rollback()
                logger.error(f"❌ КРИТИЧЕСКИЙ СБОЙ: Ошибка при сохранении структуры теста: {e}")
                raise e
            finally:
                cursor.close()
                
                
                
                
    def save_complex_test(self, header: Dict, content: List, assessment: List):
        """
        Усовершенствованная сборка теста.
        Принимает header, в котором теперь лежат и 'desc', и 'instructions'.
        """
        # Извлекаем данные из словаря header
        code = header.get('code', 'PDF_IMPORT')
        name = header.get('name', 'Новый тест')
        desc = header.get('desc', '')
        # ✅ Получаем инструкцию, если её нет — ставим пустую строку
        instr = header.get('instructions', '')

        # Создаем «шапку» теста (убедись, что твой add_test принимает 4 аргумента!)
        generated_id = self.add_test(code, name, desc, instr)
        
        # Сохраняем вопросы и шкалы
        self.save_test_structure(generated_id, content, assessment)
        
        logger.info(f"✅ Тест '{name}' со всеми описаниями успешно сохранен в БД.")

    # ==========================================================================
    # 🏁 [БЛОК 5] : ДВИЖОК АКТИВНОГО ТЕСТИРОВАНИЯ
    # ==========================================================================

    def create_test_session(self, s_id: str, t_id: str) -> str:
        sql = """
            INSERT INTO psychology.test_sessions (
                student_id, test_id, status, methodology_config
            )
            SELECT %s, t.id, 'in_progress'::psychology.session_status,
                   COALESCE(t.config, '{}'::jsonb)
                   || jsonb_build_object(
                       'test_mode',
                       COALESCE(t.config->>'test_mode', 'yes_no')
                   )
            FROM psychology.psychological_tests t
            WHERE t.id = %s::uuid AND t.is_active = TRUE
            RETURNING id;
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (s_id, t_id))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Методика {t_id} не найдена или неактивна.")
            return str(row[0])

    def get_full_test_questions(self, t_id: str) -> List[Dict[str, Any]]:
        sql = """
            SELECT id, question_text, options, order_index, question_type, media_content
            FROM psychology.test_questions
            WHERE test_id = %s AND is_active = TRUE
            ORDER BY order_index ASC;
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (t_id,))
            rows = cur.fetchall()
            media_by_question = self._get_question_media(
                cur, [str(row[0]) for row in rows]
            )
            return [
                {
                    "id": str(row[0]),
                    "text": str(row[1]),
                    "options": row[2],
                    "order": int(row[3]),
                    "question_type": str(row[4]),
                    "media_content": row[5] or {},
                    "media_assets": media_by_question.get(str(row[0]), []),
                }
                for row in rows
            ]



        

    def save_answer(
        self,
        sess_id: str,
        q_num: int,
        point_val: float,
        q_id: Optional[str] = None,
        choice_text: Optional[str] = None,
        choice_val: Optional[int] = None,
        q_text: Optional[str] = None,
        q_type: str = "single_choice",
        answer_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        💾 Сохранение ответа учащегося на вопрос теста в таблице psychology.answers.
        """
        if not q_id:
            lookup_query = """
                SELECT q.id, q.question_text 
                FROM psychology.test_questions q
                JOIN psychology.test_sessions s ON s.test_id = q.test_id
                WHERE s.id = %s AND q.order_index = %s
                LIMIT 1;
            """
            with self.get_cursor() as cur:
                cur.execute(lookup_query, (str(sess_id), int(q_num)))
                row = cur.fetchone()
                if row:
                    q_id = str(row[0])
                    if not q_text:
                        q_text = str(row[1])

        if not q_id:
            raise ValueError(
                f"Не удалось определить question_id для сессии {sess_id} и вопроса №{q_num}"
            )

        if choice_val is None:
            choice_val = 1 if float(point_val) > 0 else 0
        if choice_text is None:
            choice_text = "Да" if choice_val == 1 else "Нет"

        if answer_data is None:
            answer_data = {
                "choice": str(choice_text),
                "value": int(choice_val),
            }
        answer_payload = json.dumps(answer_data, ensure_ascii=False)

        upsert_sql = """
            INSERT INTO psychology.answers (
                session_id,
                question_id,
                question_number,
                question_text,
                question_type,
                answer_data,
                earned_score
            )
            VALUES (
                %s, 
                %s, 
                %s, 
                %s, 
                %s::psychology.question_type_enum, 
                %s::jsonb, 
                %s
            )
            ON CONFLICT (session_id, question_id) DO UPDATE SET
                question_number = EXCLUDED.question_number,
                question_text = EXCLUDED.question_text,
                question_type = EXCLUDED.question_type,
                answer_data = EXCLUDED.answer_data,
                earned_score = EXCLUDED.earned_score;
        """

        params = (
            str(sess_id),
            str(q_id),
            int(q_num),
            str(q_text) if q_text else "",
            str(q_type),
            answer_payload,
            float(point_val),
        )

        with self.get_cursor() as cur:
            cur.execute(upsert_sql, params)
            logger.debug(
                f"Ответ зафиксирован: session={sess_id}, question_id={q_id}, "
                f"№={q_num}, choice={choice_text}, score={point_val}"
            )









    def finalize_test_and_calculate(self, session_id: str, test_id: Optional[str] = None) -> None:
        """
        🚀 Высокоточный расчет итогов тестирования (Senior V13.5).
        Гарантирует наличие связей в question_scale_mapping, вызывает процедуру
        calculate_osr_session и завершает сессию.
        """
        sess_uuid = str(session_id)
        logger.info(f"Запуск расчета результатов для сессии: {sess_uuid}")

        with self.get_cursor() as cur:
            cur.execute(
                """
                    SELECT t.id, s.methodology_config
                    FROM psychology.test_sessions s
                    JOIN psychology.psychological_tests t ON t.id = s.test_id
                    WHERE s.id = %s::uuid;
                """,
                (sess_uuid,),
            )
            test_row = cur.fetchone()
            if not test_row:
                raise ValueError(f"Сессия тестирования {sess_uuid} не найдена.")

            actual_test_id = str(test_row[0])
            test_config = test_row[1] or {}
            if isinstance(test_config, str):
                test_config = json.loads(test_config)

            if test_config.get("test_mode") == "choice":
                self._calculate_choice_results(cur, sess_uuid, actual_test_id)
                cur.execute(
                    """
                        UPDATE psychology.test_sessions
                        SET status = 'completed'::psychology.session_status,
                            end_time = CURRENT_TIMESTAMP
                        WHERE id = %s::uuid;
                    """,
                    (sess_uuid,),
                )
                logger.info(
                    f"Сессия {sess_uuid} рассчитана по шкалам методики с вариантами."
                )
                return

            # 0. 🛡️ АВТО-СИНХРОНИЗАЦИЯ: проверяем наличие связей в question_scale_mapping
            cur.execute("""
                SELECT COUNT(*) 
                FROM psychology.question_scale_mapping qsm
                JOIN psychology.test_scales s ON s.id = qsm.scale_id
                WHERE s.test_id = %s::uuid AND s.is_active = TRUE;
            """, (actual_test_id,))
            mapping_count = cur.fetchone()[0]

            if mapping_count == 0:
                logger.warning(f"question_scale_mapping пуст для сессии {sess_uuid}. Выполняем авто-привязку...")
                cur.execute("SELECT test_id FROM psychology.test_sessions WHERE id = %s::uuid;", (sess_uuid,))
                t_row = cur.fetchone()
                if t_row:
                    c_tid = str(t_row[0])
                    cur.execute(
                        "SELECT id, order_index FROM psychology.test_questions "
                        "WHERE test_id = %s::uuid AND is_active = TRUE;",
                        (c_tid,),
                    )
                    q_dict = {row[1]: str(row[0]) for row in cur.fetchall()}

                    cur.execute(
                        "SELECT id, scale_code, scale_name FROM psychology.test_scales "
                        "WHERE test_id = %s::uuid AND is_active = TRUE;",
                        (c_tid,),
                    )
                    for s_id, sc_code, sc_name in cur.fetchall():
                        # Парсим номера вопросов из scale_code
                        q_nums = [int(x.strip()) for x in str(sc_code).split(',') if x.strip().isdigit()]
                        
                        # Обновляем scale_code на SCALE_N
                        s_match = re.search(r'^\s*(\d+)', str(sc_name))
                        if s_match:
                            new_code = f"SCALE_{s_match.group(1)}"
                            cur.execute("UPDATE psychology.test_scales SET scale_code = %s WHERE id = %s;", (new_code, s_id))

                        for q_num in q_nums:
                            qid = q_dict.get(q_num)
                            if qid:
                                cur.execute("""
                                    INSERT INTO psychology.question_scale_mapping (question_id, scale_id, weight)
                                    VALUES (%s, %s, 1.0)
                                    ON CONFLICT (question_id, scale_id) DO NOTHING;
                                """, (qid, str(s_id)))
                    logger.info("✅ Авто-привязка question_scale_mapping успешно завершена.")

            # 1. Запуск серверной процедуры скоринга ОСР Разуваевой
            try:
                cur.execute(
                    "SELECT psychology.calculate_osr_session(%s::uuid);",
                    (sess_uuid,)
                )
                logger.info(f"✅ Процедура calculate_osr_session успешно выполнена для сессии {sess_uuid}")
            except Exception as sp_err:
                logger.warning(f"⚠️ Ошибка вызова хранимой процедуры: {sp_err}")

            # 2. Финализируем сессию тестирования
            cur.execute("""
                UPDATE psychology.test_sessions 
                SET status = 'completed'::psychology.session_status, 
                    end_time = CURRENT_TIMESTAMP 
                WHERE id = %s::uuid;
            """, (sess_uuid,))

            logger.info(f"🏁 Сессия {sess_uuid} финализирована со статусом 'completed'.")

    @staticmethod
    def _calculate_choice_results(cursor, session_id: str, test_id: str) -> None:
        """Calculate configured scale scores from saved single/multiple selections."""
        cursor.execute(
            """
                DELETE FROM psychology.scale_results
                WHERE session_id = %s::uuid;
            """,
            (session_id,),
        )
        cursor.execute(
            """
                SELECT
                    s.id,
                    s.scale_name,
                    s.max_score,
                    s.interpretation,
                    COALESCE(SUM(COALESCE(a.earned_score, 0) * qsm.weight), 0)
                        * s.coefficient AS score
                FROM psychology.test_scales s
                JOIN psychology.question_scale_mapping qsm ON qsm.scale_id = s.id
                JOIN psychology.test_questions q
                    ON q.id = qsm.question_id AND q.is_active = TRUE
                LEFT JOIN psychology.answers a
                    ON a.question_id = q.id AND a.session_id = %s::uuid
                WHERE s.test_id = %s::uuid AND s.is_active = TRUE
                GROUP BY s.id, s.scale_name, s.max_score,
                         s.interpretation, s.coefficient
                ORDER BY s.scale_name;
            """,
            (session_id, test_id),
        )

        scale_rows = cursor.fetchall()
        summary_lines: List[str] = []
        overall_score = 0.0
        for scale_id, scale_name, max_score, interpretation, score in scale_rows:
            score_value = float(score)
            overall_score += score_value
            interpretation_text = str(interpretation or "").strip()
            scale_summary = (
                f"{scale_name}: {score_value:g} из {float(max_score):g}."
            )
            if interpretation_text:
                scale_summary = f"{scale_summary} {interpretation_text}"
            summary_lines.append(scale_summary)

            cursor.execute(
                """
                    INSERT INTO psychology.scale_results (
                        session_id, scale_id, raw_score, risk_level, interpretation
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s);
                """,
                (
                    session_id,
                    str(scale_id),
                    score_value,
                    "Рассчитан",
                    scale_summary,
                ),
            )

        if not scale_rows:
            cursor.execute(
                """
                    SELECT COALESCE(SUM(a.earned_score), 0)
                    FROM psychology.answers a
                    JOIN psychology.test_questions q ON q.id = a.question_id
                    WHERE a.session_id = %s::uuid AND q.is_active = TRUE;
                """,
                (session_id,),
            )
            overall_score = float(cursor.fetchone()[0])
            summary_lines.append(
                "Шкалы интерпретации не настроены; сохранены баллы выбранных вариантов."
            )

        cursor.execute(
            """
                INSERT INTO psychology.test_results (
                    session_id, overall_risk_level, overall_risk_score, summary
                )
                VALUES (%s::uuid, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE
                SET overall_risk_level = EXCLUDED.overall_risk_level,
                    overall_risk_score = EXCLUDED.overall_risk_score,
                    summary = EXCLUDED.summary,
                    updated_at = CURRENT_TIMESTAMP;
            """,
            (
                session_id,
                "Результат рассчитан",
                max(0, round(overall_score)),
                "\n".join(summary_lines),
            ),
        )
            

    def log_report_generation(self, session_id: str, file_path: str, generated_by: str, binary_data: bytes):
            """
            📝 Фиксация создания отчета в системном журнале test_reports.
            Позволяет хранить копию файла прямо в БД (поле file_data).
            """
            # Сначала найдем result_id для этой сессии
            get_res_query = "SELECT id FROM psychology.test_results WHERE session_id = %s;"
            
            insert_report_query = """
                INSERT INTO psychology.test_reports 
                (session_id, result_id, file_path, file_data, generated_by, report_type, report_format)
                VALUES (%s, %s, %s, %s, %s, 'full', 'docx');
            """
            
            with self.get_cursor() as cursor:
                cursor.execute(get_res_query, (session_id,))
                res_id_row = cursor.fetchone()
                result_id = res_id_row[0] if res_id_row else None
                
                # Запись самого лога и файла
                cursor.execute(insert_report_query, (
                    session_id, 
                    result_id, 
                    file_path, 
                    binary_data, # Тут сохраняется копия документа
                    generated_by
                ))
                logger.info(f"📊 Отчет для сессии {session_id} заархивирован в таблицу test_reports")
    
   
   
    # ==========================================================================
    # 🏆 [БЛОК 6] : СЛУЖБА ОТЧЕТОВ И ЖУРНАЛИРОВАНИЯ
    # ==========================================================================

    def archive_report_to_db(self, session_id: str, file_path: str, file_bytes: bytes, user_id: str):
        """
        📥 Профессиональная архивация отчета в базу данных.
        Сохраняет метаданные и само тело файла (.docx) в колонку BYTEA.
        """
        # 1. Автоматически находим связанный result_id для этой сессии
        query_result = "SELECT id FROM psychology.test_results WHERE session_id = %s;"
        
        insert_report_sql = """
            INSERT INTO psychology.test_reports 
            (session_id, result_id, file_path, file_data, generated_by, report_format, is_downloaded)
            VALUES (%s, %s, %s, %s, %s, 'docx', TRUE);
        """
        
        with self.get_cursor() as cursor:
            cursor.execute(query_result, (session_id,))
            res_row = cursor.fetchone()
            result_id = res_row[0] if res_row else None
            
            # 2. Записываем запись об отчете и сам бинарный файл
            cursor.execute(insert_report_sql, (
                session_id, 
                result_id, 
                file_path, 
                file_bytes,  # Сюда идет содержимое файла
                user_id
            ))
            logger.info(f"💾 Файл отчета заархивирован в БД для сессии: {session_id}")


     # ============================================================
    # 🏆 ОТЧЕТНОСТЬ И РЕЗУЛЬТАТЫ
    # ============================================================


    def get_test_results(self) -> List[Tuple]:
        """
        Глобальная сводка по тестированию всех учеников.
        ✅ Первой колонкой возвращаем sess.id (Session UUID).
        Это критически важно, чтобы метод get_detailed_report_data нашел сессию.
        """
        query = """
            SELECT 
                sess.id,                -- [0] Уникальный ID сессии (нужен для экспорта)
                s.student_code,         -- [1] Код ученика
                t.test_name,            -- [2] Название методики
                r.overall_risk_score,   -- [3] Набранный балл
                r.overall_risk_level,   -- [4] Категория риска
                r.created_at            -- [5] Дата завершения
            FROM psychology.test_results r
            JOIN psychology.test_sessions sess ON r.session_id = sess.id
            JOIN psychology.students s ON sess.student_id = s.id
            JOIN psychology.psychological_tests t ON sess.test_id = t.id
            ORDER BY r.created_at DESC;
        """
        with self.get_cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()

    def get_detailed_report_data(self, session_id: str) -> Dict[str, Any]:
        """
        🚀 Подготовка данных для печатного протокола DOCX (V10.5).
        Загружает ФИО, список ответов, общие итоги и детальные баллы по каждой шкале.
        [ИСПРАВЛЕНО]: Обращение к a.answer_value заменено на answer_data и earned_score.
        """
        sess_str = str(session_id)
        with self.get_cursor() as cursor:
            # 1. Загрузка данных об испытуемом, тесте и времени сессии
            query_student = """
                SELECT 
                    s.student_code,                       -- [0]
                    s.last_name_enc,                      -- [1]
                    s.first_name_enc,                     -- [2]
                    COALESCE(c.class_name, 'Не привязан'),-- [3]
                    t.test_name,                          -- [4]
                    sess.start_time,                      -- [5]
                    s.middle_name_enc,                    -- [6]
                    sess.methodology_config               -- [7]
                FROM psychology.test_sessions sess
                JOIN psychology.students s ON sess.student_id = s.id
                LEFT JOIN psychology.classes c ON s.class_id = c.id
                JOIN psychology.psychological_tests t ON sess.test_id = t.id
                WHERE sess.id = %s::uuid;
            """
            cursor.execute(query_student, (sess_str,))
            student_info = cursor.fetchone()

            if not student_info:
                logger.error(f"❌ ОШИБКА ОТЧЕТА: Сессия с ID {sess_str} не найдена.")
                return {'student': None, 'answers': [], 'summary': None, 'scales': []}

            # 2. Список ответов (Связка Вопрос <-> Выбор/Балл)
            # Берем текст выбора из JSONB или начисленный балл
            query_answers = """
                SELECT 
                    a.question_id,
                    COALESCE(a.question_text, q.question_text, 'Вопрос №' || a.question_number),
                    a.answer_data,
                    a.earned_score,
                    q.options,
                    q.media_content
                FROM psychology.answers a
                LEFT JOIN psychology.test_questions q ON a.question_id = q.id
                WHERE a.session_id = %s::uuid 
                ORDER BY a.question_number ASC;
            """
            cursor.execute(query_answers, (sess_str,))
            answer_rows = cursor.fetchall()
            media_by_question = self._get_question_media(
                cursor, [str(row[0]) for row in answer_rows]
            )
            answers_list: List[Dict[str, Any]] = []
            for row in answer_rows:
                answer_data = row[2] or {}
                if isinstance(answer_data, str):
                    answer_data = json.loads(answer_data)

                selected_ids = answer_data.get("selected_option_ids", [])
                selected_labels = answer_data.get("selected_options", [])
                if not isinstance(selected_ids, list):
                    selected_ids = []
                if not isinstance(selected_labels, list):
                    selected_labels = []
                choice = answer_data.get("choice")
                if not choice:
                    choice = ", ".join(str(label) for label in selected_labels)
                if not choice:
                    choice = str(row[3]) if row[3] is not None else "---"

                options_data = row[4] or {}
                if isinstance(options_data, str):
                    options_data = json.loads(options_data)
                options = options_data.get("options", []) if isinstance(options_data, dict) else []
                selected_media_keys = {
                    str(option.get("media_key"))
                    for option in options
                    if str(option.get("id")) in {str(value) for value in selected_ids}
                    and option.get("media_key")
                }

                media_content = row[5] or {}
                if isinstance(media_content, str):
                    media_content = json.loads(media_content)
                prompt_media_keys = {
                    str(value) for value in media_content.get("prompt_images", [])
                }
                relevant_media = [
                    asset
                    for asset in media_by_question.get(str(row[0]), [])
                    if asset["key"] in prompt_media_keys
                    or asset["key"] in selected_media_keys
                ]
                answers_list.append(
                    {
                        "question": str(row[1]),
                        "choice": str(choice),
                        "score": row[3],
                        "images": relevant_media,
                    }
                )

            # 3. Общий интегральный результат
            query_results = """
                SELECT overall_risk_score, overall_risk_level, summary 
                FROM psychology.test_results 
                WHERE session_id = %s::uuid;
            """
            cursor.execute(query_results, (sess_str,))
            result_summary = cursor.fetchone()

            # 4. Детальный профиль по шкалам (для гистограммы в Word)
            query_scales = """
                SELECT 
                    ts.scale_name,    -- [0] Название шкалы
                    sr.raw_score,     -- [1] Балл ученика
                    sr.risk_level,    -- [2] Категория риска
                    ts.max_score      -- [3] Максимальный порог
                FROM psychology.scale_results sr
                JOIN psychology.test_scales ts ON sr.scale_id = ts.id
                WHERE sr.session_id = %s::uuid
                ORDER BY ts.scale_code ASC, ts.scale_name ASC;
            """
            cursor.execute(query_scales, (sess_str,))
            scales_data = cursor.fetchall()

            test_config = student_info[7] or {}
            if isinstance(test_config, str):
                test_config = json.loads(test_config)

            # Возвращаем полный пакет данных для ReportService
            return {
                'student': student_info,
                'answers': answers_list,
                'summary': result_summary if result_summary else (0, "Норма", "Результат в норме"),
                'scales': scales_data,
                'test_mode': str(test_config.get("test_mode", "yes_no"))
            }
            

    def get_student_results(self, stud_uuid: str) -> List[Tuple]:
        """История тестирования в кабинет ученика (с детализацией Summary)."""
        query = """
            SELECT t.test_name, r.overall_risk_score, r.overall_risk_level, r.summary, r.created_at
            FROM psychology.test_results r
            JOIN psychology.test_sessions sess ON r.session_id = sess.id
            JOIN psychology.psychological_tests t ON sess.test_id = t.id
            WHERE sess.student_id = %s ORDER BY r.created_at DESC;
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, (stud_uuid,))
            return cursor.fetchall()

    def get_available_tests(self) -> List[Tuple]:
        """Все тесты, имеющие хотя бы 1 вопрос, доступные ученику."""
        sql = """
            SELECT id, test_name,
                (
                    SELECT COUNT(*)
                    FROM psychology.test_questions
                    WHERE test_id = t.id AND is_active = TRUE
                )
            FROM psychology.psychological_tests t
            WHERE is_active = TRUE
              AND EXISTS (
                  SELECT 1
                  FROM psychology.test_questions
                  WHERE test_id = t.id AND is_active = TRUE
              );
        """
        with self.get_cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()


        # ==========================================================================
    # 🧠 [БЛОК AI] : ИНТЕЛЛЕКТУАЛЬНЫЙ ПАРСЕР PDF (Senior Edition V12.0)
    # ==========================================================================

    def parse_pdf_methodology(self, file_path_src: str) -> Dict[str, Any]:
        """
        🚀 ВЫСОКОТЕХНОЛОГИЧНЫЙ AI ПАРСЕР PDF (Senior Edition V12.0).
        
        Особенности и защита:
        - Изолирует зону утверждений строго после '1. ' (исключает ложные номера из истории/описания).
        - Ищет номера только в начале строк, защищая от совпадений вида 'больницы № 20'.
        - Исключает дублирование номеров через seen_orders (защита uq_test_question_order).
        - Поддерживает дробные коэффициенты с запятыми ('1,2' -> 1.2) и max_score.
        """
        test_structure = {
            "name": "", 
            "description": "", 
            "instructions": "", 
            "questions": [], 
            "scales": []
        }
        
        try:
            with pdfplumber.open(file_path_src) as source_pdf:
                # 1. Извлечение полного сырого текста документа
                full_raw_text = "\n".join([page.extract_text() or "" for page in source_pdf.pages])

                # 2. Сепарация контента: отсекаем блок ключей, шкал и бланков
                sections = re.split(
                    r'(Ключ|Регистрационный бланк|Интерпретация|Справочные данные|Ответы на|Обработка)', 
                    full_raw_text, 
                    maxsplit=1, 
                    flags=re.IGNORECASE
                )
                question_text_zone = sections[0]

                # 3. 🛡️ СТРОГОЕ ЗОНИРОВАНИЕ: находим начало реального первого вопроса
                start_of_questions = re.search(r'(?:^|\n)\s*1\.\s+', question_text_zone)
                
                if start_of_questions:
                    # Метаданные (название, описание, инструкция) строго ДО вопроса №1
                    metadata_chunk = question_text_zone[:start_of_questions.start()].strip()
                    # Вопросы строго НАЧИНАЯ с вопроса №1
                    only_questions_zone = question_text_zone[start_of_questions.start():]
                else:
                    metadata_chunk = question_text_zone
                    only_questions_zone = question_text_zone

                # Обработка метаданных теста
                clean_lines = [line.strip() for line in metadata_chunk.split('\n') if len(line.strip()) > 3]
                if clean_lines:
                    test_structure['name'] = clean_lines[0]
                    desc_body = "\n".join(clean_lines[1:])
                    
                    if "инструкция" in desc_body.lower():
                        meta_parts = re.split(r'(Инструкция[:\s]+)', desc_body, flags=re.IGNORECASE)
                        test_structure['description'] = meta_parts[0].strip().replace('\n', ' ')
                        test_structure['instructions'] = "".join(meta_parts[1:]).strip().replace('\n', ' ')
                    else:
                        test_structure['description'] = desc_body.replace('\n', ' ')
                        test_structure['instructions'] = "Инструкция прилагается к списку утверждений."
                else:
                    test_structure['name'] = "Психологическая методика"
                    test_structure['description'] = "Диагностический опросник"
                    test_structure['instructions'] = "Внимательно прочитайте утверждения и ответьте на них."

                # 4. 📋 ПАРСИНГ ВОПРОСОВ (Только из зоны утверждений и только с начала строки)
                # Шаблон: (начало строки) -> (цифры) -> точка -> текст до следующего номера в начале строки
                q_pattern = r'(?:^|\n)\s*(\d+)\.\s*([^\n].*?)(?=(?:\n\s*\d+\.|\Z))'
                q_matches = re.findall(q_pattern, only_questions_zone, re.DOTALL)

                seen_orders = set()
                for num_str, body_text in q_matches:
                    q_num = int(num_str)
                    clean_text = " ".join(body_text.split()).strip()

                    # Жесткая защита от повторов и пустых записей
                    if q_num not in seen_orders and clean_text:
                        seen_orders.add(q_num)
                        test_structure['questions'].append({
                            'order': q_num,
                            'text': clean_text,
                            'options': json.dumps({"Да": 1, "Нет": 0}, ensure_ascii=False)
                        })

                # Гарантируем сортировку по возрастанию номеров (1..N)
                test_structure['questions'].sort(key=lambda x: x['order'])

                # 5. 📊 ПАРСИНГ ШКАЛ, КОЭФФИЦИЕНТОВ И MAX-БАЛЛОВ ИЗ ТАБЛИЦ
                seen_scales = set()
                for page in source_pdf.pages:
                    for current_table in (page.extract_tables() or []):
                        if not current_table or not current_table[0]:
                            continue

                        header_str = " ".join([str(cell).lower() for cell in current_table[0] if cell])
                        if any(keyword in header_str for keyword in ["шкала", "сужден", "номер", "коэф"]):
                            for data_row in current_table[1:]:
                                if len(data_row) >= 2 and data_row[0] and data_row[1]:
                                    scale_name = str(data_row[0]).strip().replace('\n', ' ')
                                    
                                    # Защита от дублей шкал при многостраничных таблицах
                                    if not scale_name or scale_name in seen_scales:
                                        continue

                                    seen_scales.add(scale_name)

                                    # Извлечение коэффициента
                                    coef_val = 1.0
                                    if len(data_row) > 2 and data_row[2]:
                                        try:
                                            raw_coef = str(data_row[2]).replace(',', '.').replace('\n', '').strip()
                                            coef_val = float(re.sub(r'[^\d.]', '', raw_coef))
                                        except (ValueError, TypeError):
                                            coef_val = 1.0

                                    # Извлечение Max балла
                                    max_v = 10.0
                                    if len(data_row) > 3 and data_row[3]:
                                        try:
                                            raw_max = str(data_row[3]).replace(',', '.').replace('\n', '').strip()
                                            max_v = float(re.sub(r'[^\d.]', '', raw_max))
                                        except (ValueError, TypeError):
                                            max_v = 10.0

                                    test_structure['scales'].append({
                                        'name': scale_name,
                                        'mapping': str(data_row[1]).replace(' ', '').replace('\n', ''),
                                        'coef': coef_val,
                                        'min': 0,
                                        'max': max_v,
                                        'interpretation': f"Результат анализа по шкале: '{scale_name}'"
                                    })

            logger.info(
                f"AI Success: Методика распознана успешно. "
                f"Вопросов: {len(test_structure['questions'])}, Шкал: {len(test_structure['scales'])}."
            )
            return test_structure

        except Exception as error:
            logger.error(f"SYSTEM AI_PARSER FATAL ERROR: {error}")
            traceback.print_exc()
            raise error

    # ==========================================================================
    # ⚙️ [БЛОК 8] : ТЕХНИЧЕСКОЕ ОБСЛУЖИВАНИЕ СИСТЕМЫ
    # ==========================================================================

    def get_all_users(self) -> List[Tuple]:
        """Возвращает справочник всех системных пользователей школы."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, login, role, is_active FROM psychology.users ORDER BY role ASC, login ASC;")
            return cursor.fetchall()

    def toggle_user_active(self, user_id: str, new_status: bool) -> None:
        """
        Блокировка / разблокировка учетной записи пользователя.
        :param user_id: UUID пользователя
        :param new_status: True - активен, False - заблокирован
        """
        sql = """
            UPDATE psychology.users 
            SET is_active = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s::uuid;
        """
        with self.get_cursor() as cur:
            cur.execute(sql, (bool(new_status), str(user_id)))
            logger.info(f"Пользователь ID={user_id}: статус изменен на is_active={new_status}")

    def delete_user(self, user_id: str) -> None:
        """
        Физическое удаление учетной записи пользователя из psychology.users.
        :param user_id: UUID пользователя
        """
        sql = "DELETE FROM psychology.users WHERE id = %s::uuid;"
        with self.get_cursor() as cur:
            cur.execute(sql, (str(user_id),))
            logger.warning(f"Пользователь ID={user_id} удален из базы данных.")



    # ============================================================
    # 🔔 БЛОК: УВЕДОМЛЕНИЯ И ОПОВЕЩЕНИЯ
    # ============================================================

    def get_user_notifications(self, user_id: str, only_unread: bool = False) -> List[Tuple]:
        """Получает список всех сообщений для конкретного пользователя."""
        query = """
            SELECT id, title, message, notification_type, is_read, created_at 
            FROM psychology.notifications 
            WHERE user_id = %s
        """
        if only_unread:
            query += " AND is_read = FALSE"
        
        query += " ORDER BY created_at DESC;"
        
        with self.get_cursor() as cursor:
            cursor.execute(query, (user_id,))
            return cursor.fetchall()

    def create_notification(self, user_id: str, title: str, message: str, n_type: str = 'info'):
        """Создает системное оповещение."""
        query = """
            INSERT INTO psychology.notifications (user_id, title, message, notification_type)
            VALUES (%s, %s, %s, %s);
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, (user_id, title, message, n_type))

    def mark_notification_read(self, n_id: str):
        """Помечает сообщение как прочитанное."""
        query = "UPDATE psychology.notifications SET is_read = TRUE, read_at = CURRENT_TIMESTAMP WHERE id = %s"
        with self.get_cursor() as cursor:
            cursor.execute(query, (n_id,))

    def delete_notification(self, n_id: str):
        """Удаляет сообщение."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM psychology.notifications WHERE id = %s", (n_id,))



    # ==========================================================================
    # 💾 [БЛОК: ОБСЛУЖИВАНИЕ, БЭКАПЫ И АУДИТ 152-ФЗ]
    # ==========================================================================

    def create_database_backup(self, backup_filepath: str, user_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        🚀 Создание полной резервной копии базы данных (.sql).
        Двухуровневая стратегия:
          1. Попытка нативного дампа через pg_dump.
          2. Автономный Python-экспорт данных схемы psychology (гарантия работы).
        Запись операции в psychology.backup_logs.
        """
        import os
        import subprocess
        import sys
        from datetime import datetime

        start_time = datetime.now()
        success = False
        err_msg = ""

        # --- Стратегия 1: Попытка через pg_dump ---
        pg_dump_bin = "pg_dump"
        if sys.platform == "win32":
            for ver in ["18", "17", "16", "15"]:
                candidate = f"C:\\Program Files\\PostgreSQL\\{ver}\\bin\\pg_dump.exe"
                if os.path.exists(candidate):
                    pg_dump_bin = candidate
                    break

        env = os.environ.copy()
        env["PGPASSWORD"] = str(settings.DB_PASSWORD)

        cmd = [
            pg_dump_bin,
            "-h", str(settings.DB_HOST),
            "-p", str(settings.DB_PORT),
            "-U", str(settings.DB_USER),
            "-d", str(settings.DB_NAME),
            "-n", str(settings.DB_SCHEMA),
            "-F", "p",
            "-f", backup_filepath
        ]

        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and os.path.exists(backup_filepath) and os.path.getsize(backup_filepath) > 0:
                success = True
                logger.info(f"Нативный бэкап через pg_dump успешно создан: {backup_filepath}")
            else:
                err_msg = res.stderr or "pg_dump завершился с ошибкой"
        except Exception as e:
            err_msg = str(e)

        # --- Стратегия 2: Автономный генератор SQL-дампа (Fallback) ---
        if not success:
            try:
                logger.warning(f"pg_dump недоступен ({err_msg}). Запуск встроенного генератора дампа...")
                tables = [
                    "academic_years", "schools", "classes", "students",
                    "users", "data_processing_consent", "psychological_tests",
                    "test_questions", "test_scales", "question_scale_mapping",
                    "test_sessions", "answers", "test_results", "scale_results",
                    "test_reports", "notifications"
                ]

                with self.get_cursor() as cur:
                    with open(backup_filepath, "w", encoding="utf-8") as f:
                        f.write(f"-- РЕЗЕРВНАЯ КОПИЯ: {settings.DB_NAME}\n")
                        f.write(f"-- Схема: {settings.DB_SCHEMA}\n")
                        f.write(f"-- Дата формирования: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        f.write("SET search_path TO psychology, public;\n\n")

                        for tbl in tables:
                            cur.execute(f"SELECT * FROM psychology.{tbl};")
                            rows = cur.fetchall()
                            if not rows:
                                continue
                            colnames = [d[0] for d in cur.description]
                            f.write(f"-- Таблица: {tbl} (записей: {len(rows)})\n")
                            for r in rows:
                                vals = []
                                for v in r:
                                    if v is None:
                                        vals.append("NULL")
                                    elif isinstance(v, (int, float)):
                                        vals.append(str(v))
                                    elif isinstance(v, bool):
                                        vals.append("TRUE" if v else "FALSE")
                                    elif isinstance(v, (bytes, memoryview)):
                                        vals.append(f"decode('{bytes(v).hex()}', 'hex')")
                                    elif isinstance(v, dict):
                                        esc_json = json.dumps(v, ensure_ascii=False).replace("'", "''")
                                        vals.append(f"'{esc_json}'::jsonb")
                                    else:
                                        esc_text = str(v).replace("'", "''")
                                        vals.append(f"'{esc_text}'")
                                cols_sql = ", ".join(colnames)
                                vals_sql = ", ".join(vals)
                                f.write(f"INSERT INTO psychology.{tbl} ({cols_sql}) VALUES ({vals_sql}) ON CONFLICT DO NOTHING;\n")
                            f.write("\n")
                success = True
                err_msg = ""
                logger.info(f"Встроенный SQL-дамп успешно сформирован: {backup_filepath}")
            except Exception as py_err:
                err_msg = f"Ошибка резервного копирования: {py_err}"
                logger.error(err_msg)

        # Фиксация в таблице backup_logs
        file_size = os.path.getsize(backup_filepath) if (os.path.exists(backup_filepath) and success) else 0
        end_time = datetime.now()
        status_val = "completed" if success else "failed"

        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    INSERT INTO psychology.backup_logs 
                    (backup_type, backup_path, backup_size_bytes, status, started_at, completed_at, error_message, created_by)
                    VALUES ('full', %s, %s, %s, %s, %s, %s, %s::uuid);
                """, (
                    backup_filepath,
                    file_size,
                    status_val,
                    start_time,
                    end_time,
                    err_msg if not success else None,
                    user_id
                ))
        except Exception as log_err:
            logger.error(f"Не удалось записать журнал бэкапа: {log_err}")

        return success, err_msg

    def get_last_backup_info(self) -> Optional[Dict[str, Any]]:
        """Получает информацию о последнем успешном бэкапе из базы данных."""
        try:
            with self.get_cursor() as cur:
                cur.execute("""
                    SELECT backup_path, backup_size_bytes, completed_at 
                    FROM psychology.backup_logs 
                    WHERE status = 'completed' 
                    ORDER BY completed_at DESC 
                    LIMIT 1;
                """)
                row = cur.fetchone()
                if row:
                    return {
                        "path": row[0],
                        "size": row[1] or 0,
                        "date": row[2]
                    }
        except Exception as e:
            logger.error(f"Ошибка получения данных последнего бэкапа: {e}")
        return None

    def export_audit_logs_to_excel(self, output_path: str) -> None:
        """
        📋 Выгрузка журналов безопасности и аудита действий по 152-ФЗ в Excel.
        Формирует два листа: системные действия пользователей и факты выгрузки протоколов.
        """
        import pandas as pd
        with self.get_cursor() as cur:
            # 1. Журнал аудита действий пользователей
            cur.execute("""
                SELECT 
                    a.timestamp as "Дата/Время",
                    COALESCE(u.login, 'Система') as "Пользователь",
                    COALESCE(u.role::text, '---') as "Роль",
                    a.action as "Действие",
                    a.table_name as "Таблица",
                    COALESCE(a.new_values::text, '---') as "Параметры"
                FROM psychology.audit_logs a
                LEFT JOIN psychology.users u ON a.user_id = u.id
                ORDER BY a.timestamp DESC;
            """)
            audit_rows = cur.fetchall()
            audit_cols = [desc[0] for desc in cur.description]
            df_audit = pd.DataFrame(audit_rows, columns=audit_cols)

            # 2. Журнал выгрузки психологических отчетов
            cur.execute("""
                SELECT 
                    r.generated_at as "Дата формирования",
                    COALESCE(u.login, '---') as "Сотрудник",
                    r.report_type as "Тип отчета",
                    r.report_format as "Формат",
                    COALESCE(r.file_path, 'Хранилище БД') as "Путь файла"
                FROM psychology.test_reports r
                LEFT JOIN psychology.users u ON r.generated_by = u.id
                ORDER BY r.generated_at DESC;
            """)
            rep_rows = cur.fetchall()
            rep_cols = [desc[0] for desc in cur.description]
            df_reports = pd.DataFrame(rep_rows, columns=rep_cols)

        # Excel cannot store timezone-aware timestamps; keep displayed local time.
        for dataframe in (df_audit, df_reports):
            for column in dataframe.select_dtypes(include=["datetimetz"]).columns:
                dataframe[column] = dataframe[column].dt.tz_localize(None)

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df_audit.to_excel(writer, sheet_name="Аудит действий", index=False)
            df_reports.to_excel(writer, sheet_name="Выгрузки протоколов", index=False)
        logger.info(f"Журнал аудита успешно выгружен: {output_path}")

    def change_user_password(self, user_id: str, new_password_hash: str) -> None:
        """Смена хеша пароля пользователя с фиксацией в журнале аудита."""
        with self.get_cursor() as cur:
            cur.execute("""
                UPDATE psychology.users 
                SET password_hash = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s::uuid;
            """, (new_password_hash, str(user_id)))
            
            cur.execute("""
                INSERT INTO psychology.audit_logs (user_id, action, table_name)
                VALUES (%s::uuid, 'CHANGE_PASSWORD', 'users');
            """, (str(user_id),))
            logger.info(f"Пароль пользователя ID={user_id} успешно изменен.")








    def close_all(self):
        """Безопасный разрыв всех активных коннектов и уничтожение пула (при закрытии приложения)."""
        if not self._for_tests and self._connection_pool:
            # Ожидание 1 сек перед полным освобождением ресурсов
            self._connection_pool.closeall()
            logger.info("📡 DatabaseService: Ресурсы Backend-ядра успешно освобождены.")
    
    @classmethod
    def reset_for_tests(cls):
        """Сброс состояния синглтона для чистоты изоляции unit-тестов."""
        cls._instance = None
        if cls._connection_pool:
            cls._connection_pool.closeall()
            cls._connection_pool = None