"""Общие pytest-фикстуры с безопасным разделением unit и DB tests."""

import os
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_run_db_integration_tests = os.getenv("RUN_DB_INTEGRATION_TESTS") == "1"
_requested_profile = os.getenv("DB_PROFILE", "").strip().lower()

if _run_db_integration_tests and _requested_profile != "testdb":
    raise pytest.UsageError(
        "DB integration tests require DB_PROFILE=testdb. "
        "The main .env profile is never accepted for integration tests."
    )

# Keep ordinary test runs away from the application's default .env profile.
if not _run_db_integration_tests:
    os.environ["DB_PROFILE"] = "testdb"

if _run_db_integration_tests:
    from dotenv import dotenv_values

    test_profile = dotenv_values(project_root / ".env.testdb")
    main_profile = dotenv_values(project_root / ".env")
    test_db_name = test_profile.get("DB_NAME")
    main_db_name = main_profile.get("DB_NAME", "SchoolTest")

    if not test_db_name:
        raise pytest.UsageError(
            "DB integration tests require DB_NAME in the local .env.testdb file."
        )
    if test_db_name.casefold() == str(main_db_name).casefold():
        raise pytest.UsageError(
            "The database configured in .env.testdb must differ from .env."
        )

    from config.settings import settings

    if settings.DB_NAME.casefold() != str(test_db_name).casefold():
        raise pytest.UsageError(
            "The selected database does not match DB_NAME in .env.testdb."
        )

from src.services.auth_service import AuthService  # noqa: E402
from src.services.database_service import DatabaseService  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database_service():
    """Reset the application singleton after each test."""
    yield
    DatabaseService.reset_for_tests()


@pytest.fixture
def db_service(request):
    """Create a dedicated connection pool only for explicitly enabled DB tests."""
    if request.node.get_closest_marker("integration") is None:
        pytest.fail("db_service is reserved for tests marked integration.")
    if not _run_db_integration_tests:
        pytest.skip(
            "Set DB_PROFILE=testdb and RUN_DB_INTEGRATION_TESTS=1 to run DB tests."
        )

    db = DatabaseService(for_tests=True)
    try:
        yield db
    finally:
        db.close_all()


@pytest.fixture
def fake_database():
    """A no-I/O dependency for service unit tests."""
    return object()


@pytest.fixture
def auth_service(fake_database):
    """Authentication service wired to an inert database dependency."""
    return AuthService(fake_database)


@pytest.fixture
def test_user():
    """Non-production sample data for tests."""
    return {
        "login": "test_admin",
        "password": "Test123!",
        "email": "test@school.local",
        "role": "admin",
    }
