import pytest

from src.services.tests_service import TestsService as OperationsService


class FakeDatabase:
    def __init__(self):
        self.calls = []
        self.session_owners = {"session-1": "student-1"}

    def get_test_session_student_id(self, session_id):
        self.calls.append(("get_test_session_student_id", session_id))
        return self.session_owners.get(session_id)

    def create_test_session(self, student_id, test_id):
        self.calls.append(("create_test_session", student_id, test_id))
        return "session-new"

    def save_answer(self, *args):
        self.calls.append(("save_answer", args))

    def finalize_test_and_calculate(self, *args):
        self.calls.append(("finalize_test_and_calculate", args))

    def get_student_results(self, student_id):
        self.calls.append(("get_student_results", student_id))
        return [("result",)]


def test_student_can_read_only_own_results():
    database = FakeDatabase()
    service = OperationsService(
        database, actor_role="student", actor_student_id="student-1"
    )

    assert service.get_student_results("student-1") == [("result",)]
    with pytest.raises(PermissionError, match="только свои результаты"):
        service.get_student_results("student-2")

    assert database.calls == [("get_student_results", "student-1")]


def test_student_can_create_session_only_for_self():
    database = FakeDatabase()
    service = OperationsService(
        database, actor_role="student", actor_student_id="student-1"
    )

    assert service.create_test_session("student-1", "test-1") == "session-new"
    with pytest.raises(PermissionError, match="только для себя"):
        service.create_test_session("student-2", "test-1")

    assert database.calls == [
        ("create_test_session", "student-1", "test-1")
    ]


def test_student_can_save_and_finalize_only_owned_sessions():
    database = FakeDatabase()
    service = OperationsService(
        database, actor_role="student", actor_student_id="student-1"
    )

    service.save_answer("session-1", 1, 1.0, q_id="question-1")
    service.finalize_test_and_calculate("session-1", "test-1")

    for action in (
        lambda: service.save_answer("session-other", 1, 1.0, q_id="question-1"),
        lambda: service.finalize_test_and_calculate("session-other", "test-1"),
    ):
        with pytest.raises(PermissionError, match="только со своей сессией"):
            action()

    assert [call[0] for call in database.calls] == [
        "get_test_session_student_id",
        "save_answer",
        "get_test_session_student_id",
        "finalize_test_and_calculate",
        "get_test_session_student_id",
        "get_test_session_student_id",
    ]


def test_staff_can_access_other_student_results_and_sessions():
    database = FakeDatabase()
    service = OperationsService(database, actor_role="psychologist")

    assert service.get_student_results("student-2") == [("result",)]
    service.finalize_test_and_calculate("session-1", "test-1")

    assert database.calls == [
        ("get_student_results", "student-2"),
        ("finalize_test_and_calculate", ("session-1", "test-1")),
    ]


def test_unauthenticated_or_unlinked_student_cannot_access_results():
    database = FakeDatabase()

    with pytest.raises(PermissionError):
        OperationsService(database).get_student_results("student-1")

    unlinked_student = OperationsService(database, actor_role="student")
    with pytest.raises(PermissionError):
        unlinked_student.get_student_results("student-1")

    assert database.calls == []
