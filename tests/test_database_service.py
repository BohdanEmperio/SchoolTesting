from contextlib import contextmanager
from uuid import UUID

from src.services.database_service import DatabaseService


def test_session_owner_lookup_returns_string_uuid(monkeypatch):
    service = object.__new__(DatabaseService)
    owner_id = UUID("00000000-0000-0000-0000-000000000123")

    class FakeCursor:
        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchone(self):
            return (owner_id,)

    cursor = FakeCursor()

    @contextmanager
    def fake_get_cursor():
        yield cursor

    monkeypatch.setattr(service, "get_cursor", fake_get_cursor)

    assert service.get_test_session_student_id("session-id") == str(owner_id)
    assert "WHERE id = %s::uuid" in cursor.query
    assert cursor.params == ("session-id",)


def test_session_owner_lookup_returns_none_for_missing_session(monkeypatch):
    service = object.__new__(DatabaseService)

    class FakeCursor:
        def execute(self, *_args):
            pass

        def fetchone(self):
            return None

    @contextmanager
    def fake_get_cursor():
        yield FakeCursor()

    monkeypatch.setattr(service, "get_cursor", fake_get_cursor)

    assert service.get_test_session_student_id("missing-session") is None


def test_close_all_releases_isolated_test_pool():
    service = object.__new__(DatabaseService)
    service._for_tests = True

    class FakePool:
        closed = False

        def closeall(self):
            self.closed = True

    pool = FakePool()
    service._connection_pool = pool

    service.close_all()

    assert pool.closed
    assert service._connection_pool is None
