from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_students_placeholder() -> dict:
    """Список учеников. GUI остаётся основной точкой входа в текущем проекте."""
    return {"status": "not_implemented", "message": "Логика получения списка учеников будет перенесена в сервисы"}
