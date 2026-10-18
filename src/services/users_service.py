"""Сервис работы с пользователями.

Этот модуль является безопасным промежуточным слоем для будущего переноса
логики из DatabaseService в более мелкие сервисы.

Важно: текущий GUI пока работает через DatabaseService напрямую, поэтому
этот сервис не ломает текущий сценарий запуска и не требует изменений в
существующих окнах.
"""

from typing import List, Tuple

from src.services.database_service import DatabaseService


class UsersService:
    """Композиционный слой для работы с пользователями системы."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service

    def get_all_users(self) -> List[Tuple]:
        """Возвращает всех пользователей."""
        return self.db.get_all_users()

    def toggle_user_active(self, user_id: str, new_status: bool) -> None:
        """Блокирует или разблокирует пользователя."""
        self.db.toggle_user_active(user_id, new_status)

    def delete_user(self, user_id: str) -> None:
        """Удаляет пользователя из базы."""
        self.db.delete_user(user_id)

    def get_user_notifications(self, user_id: str, only_unread: bool = False) -> List[Tuple]:
        """Возвращает уведомления для пользователя."""
        return self.db.get_user_notifications(user_id, only_unread)

    def create_notification(self, user_id: str, title: str, message: str, n_type: str = 'info') -> None:
        """Создает уведомление для пользователя."""
        self.db.create_notification(user_id, title, message, n_type)

    def mark_notification_read(self, notification_id: str) -> None:
        """Помечает уведомление как прочитанное."""
        self.db.mark_notification_read(notification_id)

    def delete_notification(self, notification_id: str) -> None:
        """Удаляет уведомление."""
        self.db.delete_notification(notification_id)
