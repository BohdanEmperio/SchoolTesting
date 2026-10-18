"""Сервис для работы с учебными классами.

Назначение: безопасное выделение логики работы с классами из DatabaseService
в отдельный модуль без ломки интерфейса.
"""

from typing import List, Tuple

from src.services.database_service import DatabaseService


class ClassesService:
    """Композиционный слой для работы с классами."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def get_all_classes(self) -> List[Tuple]:
        """Возвращает все активные классы."""
        return self.db.get_all_classes()

    def add_class(self, title: str, parallel: int, letter: str) -> str:
        """Создает класс."""
        return self.db.add_class(title, parallel, letter)

    def update_class(self, class_id: str, new_name: str) -> None:
        """Изменяет название класса."""
        self.db.update_class(class_id, new_name)

    def delete_class(self, class_id: str) -> None:
        """Удаляет класс."""
        self.db.delete_class(class_id)
