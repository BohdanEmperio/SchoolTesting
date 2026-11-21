"""Сервис для работы с учениками.

Этот модуль является безопасным шагом к разделению бизнес-логики: он
делегирует вызовы в DatabaseService, но не меняет текущий GUI-поток.
"""

from typing import List, Optional, Tuple

from src.services.database_service import DatabaseService


class StudentsService:
    """Композиционный слой для работы с данными учеников."""

    _STAFF_ROLES = frozenset({"admin", "psychologist"})
    _ADMIN_ROLES = frozenset({"admin"})

    def __init__(
        self,
        db_service: DatabaseService,
        actor_role: Optional[str],
        actor_user_id: Optional[str] = None,
    ):
        self.db = db_service
        self.actor_role = actor_role
        self.actor_user_id = str(actor_user_id) if actor_user_id is not None else None

    def _require_role(self, allowed_roles: frozenset, action: str) -> None:
        if self.actor_role not in allowed_roles:
            raise PermissionError(f"Недостаточно прав для операции: {action}.")

    def get_students_by_class(self, class_filter_uuid: str = None) -> List[Tuple]:
        """Возвращает учеников по фильтру класса."""
        self._require_role(self._STAFF_ROLES, "просмотр списка учеников")
        return self.db.get_students_by_class(class_filter_uuid)

    def add_student(
        self,
        student_code: str,
        first_name: str,
        last_name: str,
        middle_name: str,
        birth_date: str,
        gender: str,
        class_id: str,
        consent_given: bool = False,
    ) -> str:
        """Добавляет ученика."""
        self._require_role(self._STAFF_ROLES, "регистрация ученика")
        return self.db.add_student(
            student_code,
            first_name,
            last_name,
            middle_name,
            birth_date,
            gender,
            class_id,
            consent_given,
        )

    def add_student_with_account(
        self,
        student_code: str,
        first_name: str,
        last_name: str,
        middle_name: str,
        birth_date: str,
        gender: str,
        class_id: str,
        login: str,
        password_hash: str,
        consent_given: bool = False,
    ) -> str:
        """Атомарно добавляет профиль ученика и связанную учётную запись."""
        self._require_role(self._STAFF_ROLES, "регистрация ученика с учётной записью")
        return self.db.add_student_with_account(
            student_code,
            first_name,
            last_name,
            middle_name,
            birth_date,
            gender,
            class_id,
            login,
            password_hash,
            consent_given,
        )

    def update_student(self, student_id: str, first_name: str, last_name: str, middle_name: str,
                       birth_date: str, gender: str, class_id: str) -> None:
        """Обновляет данные ученика."""
        self._require_role(self._STAFF_ROLES, "изменение профиля ученика")
        self.db.update_student(student_id, first_name, last_name, middle_name, birth_date, gender, class_id)

    def delete_student(self, student_id: str) -> None:
        """Удаляет ученика."""
        self._require_role(self._ADMIN_ROLES, "удаление ученика")
        self.db.delete_student(student_id)

    def get_student_consent(self, student_uuid: str) -> bool:
        """Проверяет согласие ученика на обработку персональных данных."""
        self._require_role(self._STAFF_ROLES, "просмотр согласия на обработку данных")
        return self.db.get_student_consent(student_uuid)

    def set_student_consent(self, student_uuid: str, consent: bool = True) -> None:
        """Устанавливает согласие на обработку данных."""
        self._require_role(self._STAFF_ROLES, "изменение согласия на обработку данных")
        self.db.set_student_consent(student_uuid, consent)

    def create_student_account(self, student_uuid: str, login_str: str, hashed_pass: str) -> None:
        """Создает учетную запись ученика."""
        self._require_role(self._ADMIN_ROLES, "отдельное создание или сброс доступа ученика")
        self.db.create_student_account(student_uuid, login_str, hashed_pass)

    def revoke_student_access(self, student_uuid: str) -> None:
        """Отзывает доступ ученика."""
        self._require_role(self._ADMIN_ROLES, "отзыв доступа ученика")
        self.db.revoke_student_access(student_uuid)

    def get_student_profile(self, user_uuid: str) -> Optional[Tuple]:
        """Возвращает профиль ученика для личного кабинета."""
        if self.actor_role == "student":
            if self.actor_user_id is None or str(user_uuid) != self.actor_user_id:
                raise PermissionError("Ученик может просматривать только собственный профиль.")
        else:
            self._require_role(self._STAFF_ROLES, "просмотр профиля ученика")
        return self.db.get_student_profile(user_uuid)

    def add_imported_student(
        self,
        student_code: str,
        first_name: str,
        last_name: str,
        middle_name: str,
        birth_date: str,
        gender: str,
        class_id: str,
    ) -> str:
        """Добавляет запись через массовый импорт, доступный только администратору."""
        self._require_role(self._ADMIN_ROLES, "импорт учеников")
        return self.db.add_student(
            student_code,
            first_name,
            last_name,
            middle_name,
            birth_date,
            gender,
            class_id,
        )
