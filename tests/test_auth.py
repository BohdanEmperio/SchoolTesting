#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты аутентификации
"""

import pytest


class TestAuth:
    """Тесты аутентификации"""

    def test_password_hash(self, auth_service):
        """Проверка хеширования пароля"""
        password = "Test123!"  # ✅ Короткий пароль (< 72 байт)
        hashed = auth_service.get_password_hash(password)
        assert hashed != password
        assert hashed.startswith('$2')  # bcrypt

    def test_password_verify(self, auth_service):
        """Проверка проверки пароля"""
        password = "Test123!"  # ✅ Короткий пароль
        hashed = auth_service.get_password_hash(password)
        assert auth_service.verify_password(password, hashed)
        assert not auth_service.verify_password("wrong", hashed)

    def test_token_creation(self, auth_service):
        """Проверка создания токена"""
        data = {"sub": "test_user", "role": "admin"}
        token = auth_service.create_access_token(data)
        assert token is not None
        assert len(token) > 50

    def test_token_decode(self, auth_service):
        """Проверка декодирования токена"""
        data = {"sub": "test_user", "role": "admin"}
        token = auth_service.create_access_token(data)
        decoded = auth_service.decode_token(token)
        assert decoded["sub"] == "test_user"
        assert decoded["role"] == "admin"
    
    def test_has_active_admin_returns_database_value(self):
        class FakeCursor:
            def __init__(self, result):
                self.result = result

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, *_args):
                pass

            def fetchone(self):
                return (self.result,)

        class FakeDatabase:
            def __init__(self, result):
                self.result = result

            def get_cursor(self):
                return FakeCursor(self.result)

        from src.services.auth_service import AuthService

        assert AuthService(FakeDatabase(True)).has_active_admin()
        assert not AuthService(FakeDatabase(False)).has_active_admin()

    def test_has_active_admin_fails_closed(self):
        class UnavailableDatabase:
            def get_cursor(self):
                raise ConnectionError("database unavailable")

        from src.services.auth_service import AuthService

        assert AuthService(UnavailableDatabase()).has_active_admin()

    @pytest.mark.parametrize(
        ("login", "email", "password", "confirm"),
        [
            ("ab", "user@example.test", "Password123", "Password123"),
            ("valid_user", "invalid-email", "Password123", "Password123"),
            ("valid_user", "user@example.test", "short", "short"),
            ("valid_user", "user@example.test", "Password123", "Different123"),
        ],
    )
    def test_staff_registration_rejects_invalid_input(
        self, auth_service, login, email, password, confirm
    ):
        from src.services.auth_service import RegistrationError

        with pytest.raises(RegistrationError):
            auth_service.register_staff(
                login, email, password, confirm, "psychologist"
            )

    def test_staff_registration_rejects_student_role_before_database_access(self):
        from src.services.auth_service import AuthService, RegistrationError

        class UnavailableDatabase:
            def get_cursor(self):
                raise AssertionError("Invalid roles must be rejected before DB access.")

        service = AuthService(UnavailableDatabase())
        with pytest.raises(RegistrationError, match="Недопустимая роль"):
            service.register_staff(
                "new_staff", None, "Password123", "Password123", "student"
            )

    @pytest.mark.parametrize(
        ("has_admin", "created_by", "role", "expected_error"),
        [
            (False, None, "psychologist", "Сначала создайте"),
            (
                True,
                {"role": "psychologist"},
                "psychologist",
                "только администратор",
            ),
        ],
    )
    def test_staff_registration_enforces_first_admin_and_admin_creator_rules(
        self, has_admin, created_by, role, expected_error
    ):
        from src.services.auth_service import AuthService, RegistrationError

        database = RegistrationDatabase(has_admin=has_admin)
        service = AuthService(database)

        with pytest.raises(RegistrationError, match=expected_error):
            service.register_staff(
                "new_staff",
                None,
                "Password123",
                "Password123",
                role,
                created_by=created_by,
            )

        assert not database.inserted_values

    def test_admin_can_create_staff_account_with_hashed_password(self):
        from src.services.auth_service import AuthService

        database = RegistrationDatabase(has_admin=True)
        service = AuthService(database)

        new_user_id = service.register_staff(
            "new_staff",
            "new_staff@example.test",
            "Password123",
            "Password123",
            "psychologist",
            created_by={"role": "admin", "login": "admin"},
        )

        assert new_user_id == "new-user-id"
        inserted_password = database.inserted_values[2]
        assert inserted_password != "Password123"
        assert service.verify_password("Password123", inserted_password)


class RegistrationDatabase:
    def __init__(self, has_admin):
        self.has_admin = has_admin
        self.inserted_values = None

    def get_cursor(self):
        return RegistrationCursor(self)


class RegistrationCursor:
    def __init__(self, database):
        self.database = database
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split())
        if "SELECT EXISTS" in normalized_query:
            self.result = (self.database.has_admin,)
        elif normalized_query.startswith("SELECT 1 FROM psychology.users"):
            self.result = None
        elif normalized_query.startswith("INSERT INTO psychology.users"):
            self.database.inserted_values = params
            self.result = ("new-user-id",)

    def fetchone(self):
        return self.result
