from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def admin_placeholder() -> dict:
    """Административный API-слой. Пока служит каркасом для будущей интеграции."""
    return {"status": "not_implemented", "message": "Административный слой будет добавлен после стабилизации основного GUI"}
