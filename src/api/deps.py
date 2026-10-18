from typing import Generator

from src.services.database_service import DatabaseService


def get_db_service() -> Generator[DatabaseService, None, None]:
    """Возвращает сервис БД для API-слоя.

    В текущем состоянии GUI остаётся основным интерфейсом, а API является
    отдельным расширением и не должен ломать существующий сценарий запуска.
    """
    db_service = DatabaseService()
    yield db_service
