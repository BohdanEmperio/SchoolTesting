from fastapi import FastAPI

from src.api.routes import admin, auth, students, tests

app = FastAPI(
    title="School Psychology Testing API",
    version="0.1.0",
    description="Отдельный слой API для интеграции с GUI и будущими внешними сервисами.",
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(students.router, prefix="/api/students", tags=["students"])
app.include_router(tests.router, prefix="/api/tests", tags=["tests"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/health")
def health_check() -> dict:
    """Проверка доступности API-слоя."""
    return {"status": "ok", "service": "school_psychology_api"}
