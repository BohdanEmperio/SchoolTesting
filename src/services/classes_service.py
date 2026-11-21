"""Сервис для работы с учебными классами.

Назначение: безопасное выделение логики работы с классами из DatabaseService
в отдельный модуль без ломки интерфейса.
"""

import re
from typing import List, Optional, Tuple

from src.services.database_service import DatabaseService


class ClassesService:
    """Композиционный слой для работы с классами."""

    _CLASS_NAME_PATTERN = re.compile(r"(\d{1,2})\s*([A-Za-zА-Яа-яЁё])")
    _CLASS_READER_ROLES = frozenset({"admin", "psychologist"})

    def __init__(self, db_service: DatabaseService, actor_role: Optional[str]):
        self.db = db_service
        self.actor_role = actor_role

    def _require_role(self, allowed_roles: frozenset, action: str) -> None:
        if self.actor_role not in allowed_roles:
            raise PermissionError(f"Недостаточно прав для операции: {action}.")

    @classmethod
    def parse_class_name(cls, name: str) -> Tuple[str, int, str]:
        """Проверяет обозначение класса и возвращает имя, параллель и букву."""
        match = cls._CLASS_NAME_PATTERN.fullmatch((name or "").strip())
        if not match:
            raise ValueError("Введите класс в формате «5Б» (номер и одна буква).")

        grade = int(match.group(1))
        if grade < 1:
            raise ValueError("Номер класса должен быть положительным числом.")
        letter = match.group(2).upper()
        return f"{grade}{letter}", grade, letter

    def get_all_classes(self) -> List[Tuple]:
        """Возвращает все активные классы."""
        self._require_role(self._CLASS_READER_ROLES, "просмотр классов")
        return self.db.get_all_classes()

    def add_class(self, title: str, parallel: int, letter: str) -> str:
        """Создает класс."""
        self._require_role(self._CLASS_READER_ROLES, "создание класса")
        return self.db.add_class(title, parallel, letter)

    def update_class(self, class_id: str, new_name: str) -> None:
        """Изменяет название класса."""
        self._require_role(self._CLASS_READER_ROLES, "изменение класса")
        name, grade, letter = self.parse_class_name(new_name)
        self.db.update_class(class_id, name, grade, letter)

    def delete_class(self, class_id: str) -> None:
        """Удаляет класс."""
        self._require_role(frozenset({"admin"}), "удаление класса")
        self.db.delete_class(class_id)
