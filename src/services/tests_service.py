"""Сервис для работы с психологическими тестами.

Назначение: выделить логику методик и результатов из DatabaseService в
отдельный слой, при этом не ломая текущий GUI-процесс.
"""

from typing import Any, Dict, List, Optional, Tuple

from src.services.database_service import DatabaseService


class TestsService:
    """Композиционный слой для работы с тестами."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def get_all_tests(self) -> List[Tuple]:
        """Возвращает список всех активных тестов."""
        return self.db.get_all_tests()

    def add_test(
        self,
        code: str,
        name: str,
        desc: str,
        instructions: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Добавляет новый тест."""
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
        self.db.update_test_metadata(test_id, code, name, desc, instr, config)

    def delete_test(self, test_id: str) -> None:
        """Удаляет тест."""
        self.db.delete_test(test_id)

    def get_test_full_structure(
        self, test_id: str
    ) -> Tuple[List[Dict[str, Any]], List[Tuple], Dict[str, str]]:
        """Возвращает структуру теста."""
        return self.db.get_test_full_structure(test_id)

    def save_test_structure(
        self,
        test_id: str,
        questions: List[Dict[str, Any]],
        scales: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Сохраняет структуру теста."""
        self.db.save_test_structure(test_id, questions, scales, metadata)

    def create_test_session(self, student_id: str, test_id: str) -> str:
        """Создает сессию прохождения теста."""
        return self.db.create_test_session(student_id, test_id)

    def get_full_test_questions(self, test_id: str) -> List[Dict[str, Any]]:
        """Возвращает список вопросов для прохождения теста."""
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
        self.db.finalize_test_and_calculate(session_id, test_id)

    def get_student_results(self, student_uuid: str) -> List[Tuple]:
        """Возвращает результаты тестирования для ученика."""
        return self.db.get_student_results(student_uuid)

    def get_test_results(self) -> List[Tuple]:
        """Возвращает результаты всех тестов."""
        return self.db.get_test_results()
