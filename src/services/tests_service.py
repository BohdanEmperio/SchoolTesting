"""Сервис для работы с психологическими тестами.

Назначение: выделить логику методик и результатов из DatabaseService в
отдельный слой, при этом не ломая текущий GUI-процесс.
"""

from typing import Any, Dict, List, Optional, Tuple

from src.services.database_service import DatabaseService


class TestsService:
    """Test operations with role and student-session ownership checks."""

    _STAFF_ROLES = frozenset({"admin", "psychologist"})
    _TEST_ROLES = frozenset({"admin", "psychologist", "student"})

    def __init__(
        self,
        db_service: DatabaseService,
        actor_role: Optional[str] = None,
        actor_student_id: Optional[str] = None,
    ):
        self.db = db_service
        self.actor_role = actor_role
        self.actor_student_id = (
            str(actor_student_id) if actor_student_id is not None else None
        )

    def _require_role(self, allowed_roles: frozenset, action: str) -> None:
        if self.actor_role not in allowed_roles:
            raise PermissionError(f"Недостаточно прав для операции: {action}.")

    def _require_session_access(self, session_id: str, action: str) -> None:
        self._require_role(self._TEST_ROLES, action)
        if self.actor_role in self._STAFF_ROLES:
            return

        owner_id = self.db.get_test_session_student_id(str(session_id))
        if (
            self.actor_student_id is None
            or owner_id is None
            or str(owner_id) != self.actor_student_id
        ):
            raise PermissionError("Ученик может работать только со своей сессией.")

    def get_all_tests(self) -> List[Tuple]:
        """Возвращает список всех активных тестов."""
        self._require_role(self._STAFF_ROLES, "просмотр списка методик")
        return self.db.get_all_tests()

    def get_available_tests(self) -> List[Tuple]:
        """Возвращает активные методики, доступные ученику."""
        self._require_role(self._TEST_ROLES, "просмотр доступных методик")
        return self.db.get_available_tests()

    def add_test(
        self,
        code: str,
        name: str,
        desc: str,
        instructions: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Добавляет новый тест."""
        self._require_role(self._STAFF_ROLES, "создание методики")
        return self.db.add_test(code, name, desc, instructions, config)

    def update_test_metadata(
        self,
        test_id: str,
        code: str,
        name: str,
        desc: str,
        instr: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Обновляет метаданные теста."""
        self._require_role(self._STAFF_ROLES, "изменение методики")
        self.db.update_test_metadata(test_id, code, name, desc, instr, config)

    def delete_test(self, test_id: str) -> None:
        """Удаляет тест."""
        self._require_role(self._STAFF_ROLES, "удаление методики")
        self.db.delete_test(test_id)

    def get_test_full_structure(
        self, test_id: str
    ) -> Tuple[List[Dict[str, Any]], List[Tuple], Dict[str, str]]:
        """Возвращает структуру теста."""
        self._require_role(self._TEST_ROLES, "просмотр структуры методики")
        return self.db.get_test_full_structure(test_id)

    def save_test_structure(
        self,
        test_id: str,
        questions: List[Dict[str, Any]],
        scales: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Сохраняет структуру теста."""
        self._require_role(self._STAFF_ROLES, "изменение структуры методики")
        self.db.save_test_structure(test_id, questions, scales, metadata)

    def create_test_session(self, student_id: str, test_id: str) -> str:
        """Создает сессию прохождения теста."""
        self._require_role(self._TEST_ROLES, "создание сессии тестирования")
        if (
            self.actor_role == "student"
            and (
                self.actor_student_id is None
                or str(student_id) != self.actor_student_id
            )
        ):
            raise PermissionError("Ученик может создавать сессию только для себя.")
        return self.db.create_test_session(student_id, test_id)

    def get_full_test_questions(self, test_id: str) -> List[Dict[str, Any]]:
        """Возвращает список вопросов для прохождения теста."""
        self._require_role(self._TEST_ROLES, "просмотр вопросов методики")
        return self.db.get_full_test_questions(test_id)

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
        """Сохраняет ответ в сессию."""
        self._require_session_access(sess_id, "сохранение ответа")
        self.db.save_answer(
            sess_id,
            q_num,
            point_val,
            q_id,
            choice_text,
            choice_val,
            q_text,
            q_type,
            answer_data,
        )

    def finalize_test_and_calculate(self, session_id: str, test_id: Optional[str] = None) -> None:
        """Завершает тест и вычисляет итоговые результаты."""
        self._require_session_access(session_id, "завершение сессии тестирования")
        self.db.finalize_test_and_calculate(session_id, test_id)

    def get_student_results(self, student_uuid: str) -> List[Tuple]:
        """Возвращает результаты тестирования для ученика."""
        self._require_role(self._TEST_ROLES, "просмотр результатов ученика")
        if (
            self.actor_role == "student"
            and (
                self.actor_student_id is None
                or str(student_uuid) != self.actor_student_id
            )
        ):
            raise PermissionError("Ученик может просматривать только свои результаты.")
        return self.db.get_student_results(student_uuid)

    def get_test_results(self) -> List[Tuple]:
        """Возвращает результаты всех тестов."""
        self._require_role(self._STAFF_ROLES, "просмотр результатов тестирования")
        return self.db.get_test_results()
