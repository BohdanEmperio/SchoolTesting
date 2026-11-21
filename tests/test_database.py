"""Read-only PostgreSQL schema integration checks."""

import pytest
from config.settings import settings

pytestmark = pytest.mark.integration


class TestDatabase:
    """Tests that require the isolated test database."""

    def test_schema_exists(self, db_service):
        with db_service.get_cursor() as cursor:
            cursor.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name = %s
            """, (settings.DB_SCHEMA,))
            result = cursor.fetchone()
            assert result is not None

    def test_required_tables_exist(self, db_service):
        required_tables = {
            "users",
            "students",
            "classes",
            "test_sessions",
            "test_results",
        }
        with db_service.get_cursor() as cursor:
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = ANY(%s)
            """, (settings.DB_SCHEMA, sorted(required_tables)))
            existing_tables = {row[0] for row in cursor.fetchall()}

        assert existing_tables == required_tables

    def test_users_table_has_authentication_columns(self, db_service):
        with db_service.get_cursor() as cursor:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'users'
                  AND column_name = ANY(%s)
            """, (settings.DB_SCHEMA, ["login", "password_hash", "role", "is_active"]))
            columns = {row[0] for row in cursor.fetchall()}

        assert columns == {"login", "password_hash", "role", "is_active"}