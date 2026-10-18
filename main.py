#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# === ИСПРАВЛЕНИЕ ===
# Убеждаемся, что папка logs существует. Если нет - создаем её.
log_dir = project_root / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
log_file_path = log_dir / 'app.log'
# ===================

# Настраиваем логирование ПЕРЕД импортом тяжелых модулей
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'), # Используем абсолютный путь
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Точка входа с отложенной загрузкой тяжелых библиотек."""
    try:
        logger.info("🚀 Старт инициализации...")

        # 1. Загружаем GUI ядро (оно легкое)
        from PySide6.QtGui import QColor, QFont, QPalette
        from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
        from src.gui.styles.live_reload import StyleSheetReloader

        app = QApplication(sys.argv)
        _style_reloader = StyleSheetReloader(app)
        app.setStyle("Fusion")
        app.setFont(QFont("Segoe UI", 10))

        # 2. Настраиваем палитру
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(245, 245, 245))
        palette.setColor(QPalette.WindowText, QColor(51, 51, 51))
        palette.setColor(QPalette.Button, QColor(245, 245, 245))
        palette.setColor(QPalette.Highlight, QColor(76, 175, 80))
        app.setPalette(palette)

        # 3. ИМПОРТИРУЕМ ОСТАЛЬНОЕ ТОЛЬКО ЗДЕСЬ (внутри функции)
        # Это заставит Python грузить pydantic и базу ПОСЛЕ запуска GUI движка
        logger.info("📊 Подключение системных сервисов...")
        from src.gui.auth_window import AuthWindow
        from src.gui.main_window import MainWindow
        from src.services.auth_service import AuthService
        from src.services.database_service import DatabaseService
    

        db_service = DatabaseService()
        if not db_service.ping():
            logger.critical("❌ Невозможно установить соединение с PostgreSQL. Проверьте .env и доступность БД.")
            QMessageBox.critical(
                None,
                "Ошибка подключения к БД",
                "Не удалось подключиться к PostgreSQL. Проверьте настройки в .env, имя базы данных и доступность сервера.",
            )
            return

        auth_service = AuthService(db_service)

        logger.info("🔐 Запуск окна авторизации...")
        auth_window = AuthWindow(auth_service)
        
        # Запускаем модальный вход
        if auth_window.exec() == QDialog.Accepted:
            user_data = auth_window.get_user_data()
            logger.info(f"✅ Вход: {user_data.get('login')}")
            
            # Показываем главное окно
            main_win = MainWindow(auth_service, db_service, user_data=user_data)
            main_win.show()
            
            sys.exit(app.exec())
        else:
            logger.info("🚪 Приложение закрыто.")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"💥 Критический сбой при запуске: {e}")
        # Печатаем полный текст ошибки для нас с тобой
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()