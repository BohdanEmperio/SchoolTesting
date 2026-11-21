import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMessageBox,
    QPushButton,
    QWidget,
)

from src.gui.admin.admin_dashboard import AdminDashboard, StudentDialog
from src.gui.psychologist.psychologist_dashboard import PsychologistDashboard
from src.gui.student.student_dashboard import StudentDashboard
from src.services.tests_service import TestsService as RoleAwareTestsService


class DashboardDatabase:
    def __init__(self):
        self.calls = []

    def get_all_classes(self):
        return [("class-1", "5Б", 5, 0)]

    def get_students_by_class(self, class_id=None):
        return []

    def get_test_results(self):
        return []

    def get_all_tests(self):
        return []

    def get_user_notifications(self, user_id, only_unread=False):
        return []

    def add_student_with_account(self, *args):
        self.calls.append(("add_student_with_account", args))
        return "student-id"

    def add_student(self, *args):
        self.calls.append(("add_student", args))
        return "student-id"

    def get_student_profile(self, user_id):
        self.calls.append(("get_student_profile", user_id))
        return (b"First", b"Last", "5Б")

    def get_available_tests(self):
        self.calls.append(("get_available_tests",))
        return []

    def get_student_results(self, student_id):
        self.calls.append(("get_student_results", student_id))
        return []


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def psychologist_dashboard(qapp):
    dashboard = PsychologistDashboard(
        None,
        DashboardDatabase(),
        {"id": "psychologist-id", "login": "psychologist", "role": "psychologist"},
    )
    yield dashboard
    dashboard.close()


def test_psychologist_can_manage_but_not_delete_classes(psychologist_dashboard):
    dashboard = psychologist_dashboard
    tab_names = [
        dashboard.tabs.tabText(index) for index in range(dashboard.tabs.count())
    ]
    classes_index = next(
        index for index, name in enumerate(tab_names) if "Классы" in name
    )
    class_buttons = dashboard.tabs.widget(classes_index).findChildren(QPushButton)
    buttons_by_text = {button.text(): button for button in class_buttons}

    assert buttons_by_text["➕ Добавить класс"].isEnabled()
    assert buttons_by_text["✏️ Переименовать"].isEnabled()
    assert not buttons_by_text["🗑️ Расформировать"].isEnabled()
    assert dashboard.tabs.count() == 4


def test_double_clicking_class_filters_student_list(psychologist_dashboard):
    dashboard = psychologist_dashboard
    dashboard.on_class_double_clicked(0, 0)

    assert dashboard.tabs.currentIndex() == dashboard.students_tab_index
    assert dashboard.student_class_filter.currentData() == "class-1"


def test_psychologist_cannot_delete_class_by_direct_slot(
    psychologist_dashboard, monkeypatch
):
    warnings = []
    monkeypatch.setattr(
        "src.gui.admin.admin_dashboard.QMessageBox.warning",
        lambda *args: warnings.append(args),
    )

    psychologist_dashboard.on_delete_class_clicked()

    assert warnings


class MinimalAdminDashboard(AdminDashboard):
    def create_main_tab(self):
        return QWidget()

    def create_users_tab(self):
        return QWidget()

    def create_students_tab(self):
        return QWidget()

    def create_results_tab(self):
        return QWidget()

    def create_tests_tab(self):
        return QWidget()

    def create_schools_tab(self):
        return QWidget()

    def create_settings_tab(self):
        return QWidget()

    def manual_refresh_all(self):
        pass


def test_admin_retains_class_deletion_access(qapp):
    dashboard = MinimalAdminDashboard(
        None,
        DashboardDatabase(),
        {"id": "admin-id", "login": "admin", "role": "admin"},
    )
    class_tab = next(
        dashboard.tabs.widget(index)
        for index in range(dashboard.tabs.count())
        if "Классы" in dashboard.tabs.tabText(index)
    )
    delete_button = next(
        button
        for button in class_tab.findChildren(QPushButton)
        if button.text() == "🗑️ Расформировать"
    )

    assert dashboard.tabs.count() == 8
    assert delete_button.isEnabled()
    dashboard.close()


@pytest.mark.parametrize("create_account", [True, False])
def test_psychologist_can_register_student_from_dashboard(
    qapp, monkeypatch, create_account
):
    database = DashboardDatabase()
    hashed_passwords = []

    class FakeAuthService:
        def get_password_hash(self, password):
            hashed_passwords.append(password)
            return "bcrypt-hash"

    dashboard = MinimalAdminDashboard(
        FakeAuthService(),
        database,
        {"id": "psychologist-id", "login": "psychologist", "role": "psychologist"},
    )

    def accept_student_dialog(dialog):
        dialog.in_fn.setText("First")
        dialog.in_ln.setText("Last")
        dialog.in_mn.setText("")
        dialog.in_consent.setChecked(True)
        dialog.login_input.setText("student_1")
        dialog.password_input.setText("Student123!")
        dialog.confirm_password_input.setText("Student123!")
        dialog.create_account_check.setChecked(create_account)
        dialog.do_validate()
        return dialog.result()

    monkeypatch.setattr(StudentDialog, "exec", accept_student_dialog)
    monkeypatch.setattr(
        "src.gui.admin.admin_dashboard.QMessageBox.information", lambda *args: None
    )
    dashboard.on_add_student_clicked()

    expected_method = (
        "add_student_with_account" if create_account else "add_student"
    )
    assert [call[0] for call in database.calls] == [expected_method]
    assert hashed_passwords == (["Student123!"] if create_account else [])
    dashboard.close()


def test_student_dashboard_loads_results_for_linked_student(qapp):
    database = DashboardDatabase()
    dashboard = StudentDashboard(
        None,
        database,
        {
            "id": "student-user-id",
            "student_id": "student-id",
            "login": "student",
            "role": "student",
        },
    )

    assert ("get_student_profile", "student-user-id") in database.calls
    assert ("get_available_tests",) in database.calls
    assert ("get_student_results", "student-id") in database.calls
    dashboard.close()


def test_student_test_view_uses_owned_session_service(qapp, monkeypatch):
    from src.gui.student.test_taking_view import TestTakingView

    class SessionDatabase(DashboardDatabase):
        def create_test_session(self, student_id, test_id):
            self.calls.append(("create_test_session", student_id, test_id))
            return "session-id"

        def get_full_test_questions(self, test_id):
            self.calls.append(("get_full_test_questions", test_id))
            return [
                {
                    "id": "question-id",
                    "text": "Question",
                    "order": 1,
                    "question_type": "single_choice",
                    "options": {"Да": 1, "Нет": 0},
                }
            ]

        def get_test_session_student_id(self, session_id):
            self.calls.append(("get_test_session_student_id", session_id))
            return "student-id"

        def save_answer(self, *args):
            self.calls.append(("save_answer", args))

        def finalize_test_and_calculate(self, *args):
            self.calls.append(("finalize_test_and_calculate", args))

    database = SessionDatabase()
    service = RoleAwareTestsService(
        database, actor_role="student", actor_student_id="student-id"
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)

    dialog = TestTakingView(
        tests_service=service,
        test_id="test-id",
        test_name="Test",
        student_id="student-id",
    )
    dialog.on_answer_submitted(1)

    assert [call[0] for call in database.calls] == [
        "create_test_session",
        "get_full_test_questions",
        "get_test_session_student_id",
        "save_answer",
        "get_test_session_student_id",
        "finalize_test_and_calculate",
    ]
    assert dialog.result() == QDialog.Accepted
    dialog.close()
