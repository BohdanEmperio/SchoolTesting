# Документация проекта

В этом разделе собраны краткие материалы по ключевым модулям, архитектуре и безопасному развитию проекта.

## Основные документы

- [API.md](API.md) — описание API-слоя.
- [DATABASE.md](DATABASE.md) — описание схемы данных.
- [MODULES_REFERENCE.md](MODULES_REFERENCE.md) — список ключевых модулей.

## Основные модули

- [main.py](../main.py) — стартовая точка приложения.
- [config/settings.py](../config/settings.py) — настройки окружения.
- [src/services/auth_service.py](../src/services/auth_service.py) — аутентификация и JWT.
- [src/services/database_service.py](../src/services/database_service.py) — работа с PostgreSQL.
- [src/gui/main_window.py](../src/gui/main_window.py) — маршрутизация по ролям.
- [src/gui/admin/admin_dashboard.py](../src/gui/admin/admin_dashboard.py) — интерфейс администратора.
- [src/gui/student/student_dashboard.py](../src/gui/student/student_dashboard.py) — кабинет ученика.
