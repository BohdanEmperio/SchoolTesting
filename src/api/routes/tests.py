from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_tests_placeholder() -> dict:
    """Список доступных методик. GUI остаётся основным интерфейсом пользователя."""
    return {"status": "not_implemented", "message": "Логика методик будет вынесена из GUI в сервисы"}
