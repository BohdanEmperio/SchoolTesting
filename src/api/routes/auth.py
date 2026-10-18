from fastapi import APIRouter

router = APIRouter()


@router.get("/login")
def login_placeholder() -> dict:
    """Сервис входа. Реальный код лучше держать в src/services/auth_service.py.

    Этот маршрут создан как безопасный каркас для дальнейшей интеграции,
    чтобы не ломать уже работающий GUI-цикл.
    """
    return {"status": "not_implemented", "message": "Логика входа реализуется в сервисах проекта"}
