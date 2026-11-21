import pytest

from src.services.students_service import StudentsService


class FakeDatabase:
    def __init__(self):
        self.calls = []

    def __getattr__(self, method_name):
        def record_call(*args):
            self.calls.append((method_name, args))
            if method_name.startswith("get_"):
                return [] if method_name == "get_students_by_class" else True
            return "student-id"

        return record_call


def test_psychologist_can_register_student_with_account():
    database = FakeDatabase()
    service = StudentsService(database, actor_role="psychologist")

    student_id = service.add_student_with_account(
        "2026-ABC",
        "First",
        "Last",
        "",
        "2016-01-01",
        "Не указан",
        "class-id",
        "student_login",
        "bcrypt-hash",
        True,
    )

    assert student_id == "student-id"
    assert database.calls[0][0] == "add_student_with_account"


def test_psychologist_can_update_profile_and_consent():
    database = FakeDatabase()
    service = StudentsService(database, actor_role="psychologist")

    service.update_student(
        "student-id", "First", "Last", "", "2016-01-01", "Не указан", "class-id"
    )
    assert service.get_student_consent("student-id") is True
    service.set_student_consent("student-id", False)

    assert [call[0] for call in database.calls] == [
        "update_student",
        "get_student_consent",
        "set_student_consent",
    ]


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("delete_student", ("student-id",)),
        ("create_student_account", ("student-id", "login", "hash")),
        ("revoke_student_access", ("student-id",)),
        (
            "add_imported_student",
            ("code", "first", "last", "", "2016-01-01", "Не указан", "class-id"),
        ),
    ],
)
def test_psychologist_cannot_use_admin_only_student_operations(method_name, args):
    database = FakeDatabase()
    service = StudentsService(database, actor_role="psychologist")

    with pytest.raises(PermissionError):
        getattr(service, method_name)(*args)

    assert database.calls == []


def test_student_can_read_only_own_profile():
    database = FakeDatabase()
    service = StudentsService(
        database,
        actor_role="student",
        actor_user_id="own-user-id",
    )

    assert service.get_student_profile("own-user-id") is True
    assert database.calls == [("get_student_profile", ("own-user-id",))]

    with pytest.raises(PermissionError, match="собственный профиль"):
        service.get_student_profile("other-user-id")

    assert len(database.calls) == 1


def test_student_cannot_read_staff_student_list_or_register_students():
    database = FakeDatabase()
    service = StudentsService(
        database,
        actor_role="student",
        actor_user_id="own-user-id",
    )

    with pytest.raises(PermissionError):
        service.get_students_by_class()
    with pytest.raises(PermissionError):
        service.add_student(
            "code",
            "First",
            "Last",
            "",
            "2016-01-01",
            "Не указан",
            "class-id",
        )

    assert database.calls == []


def test_student_cannot_change_profile_or_consent():
    database = FakeDatabase()
    service = StudentsService(
        database, actor_role="student", actor_user_id="own-user-id"
    )

    with pytest.raises(PermissionError):
        service.update_student(
            "student-id", "First", "Last", "", "2016-01-01", "Не указан", "class-id"
        )
    with pytest.raises(PermissionError):
        service.get_student_consent("student-id")
    with pytest.raises(PermissionError):
        service.set_student_consent("student-id", True)

    assert database.calls == []


def test_admin_can_use_admin_only_student_operations():
    database = FakeDatabase()
    service = StudentsService(database, actor_role="admin")

    service.delete_student("student-id")
    service.create_student_account("student-id", "login", "hash")
    service.revoke_student_access("student-id")
    service.add_imported_student(
        "code",
        "First",
        "Last",
        "",
        "2016-01-01",
        "Не указан",
        "class-id",
    )

    assert [call[0] for call in database.calls] == [
        "delete_student",
        "create_student_account",
        "revoke_student_access",
        "add_student",
    ]
