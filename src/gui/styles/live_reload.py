"""Загрузка и live reload общей темы QSS во время разработки."""

import logging
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer
from PySide6.QtWidgets import QApplication


logger = logging.getLogger(__name__)
STYLESHEET_PATH = Path(__file__).with_name("main.qss")


def load_stylesheet() -> str:
    """Читает актуальную таблицу стилей приложения."""
    return STYLESHEET_PATH.read_text(encoding="utf-8")


class StyleSheetReloader(QObject):
    """Применяет сохранённые изменения QSS к уже открытым окнам."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stylesheet = load_stylesheet()
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._schedule_reload)
        self._watcher.directoryChanged.connect(self._on_directory_changed)
        self._watcher.addPath(str(STYLESHEET_PATH.parent))
        self._ensure_file_watch()

        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(200)
        self._reload_timer.timeout.connect(self._reload_stylesheet)

    def _schedule_reload(self, _path: str = "") -> None:
        self._reload_timer.start()

    def _on_directory_changed(self, _path: str) -> None:
        self._ensure_file_watch()
        self._schedule_reload()

    def _ensure_file_watch(self) -> None:
        stylesheet_path = str(STYLESHEET_PATH)
        if STYLESHEET_PATH.exists() and stylesheet_path not in self._watcher.files():
            self._watcher.addPath(stylesheet_path)

    def _reload_stylesheet(self) -> None:
        self._ensure_file_watch()
        try:
            updated_stylesheet = load_stylesheet()
        except OSError:
            logger.exception("Не удалось прочитать QSS после изменения файла.")
            return

        if not updated_stylesheet.strip():
            logger.warning("Пустой QSS не применён; текущая тема сохранена.")
            return
        if updated_stylesheet == self._stylesheet:
            return

        previous_stylesheet = self._stylesheet
        application = QApplication.instance()
        if application:
            for widget in application.allWidgets():
                if widget.styleSheet() == previous_stylesheet:
                    widget.setStyleSheet(updated_stylesheet)

        self._stylesheet = updated_stylesheet
        logger.info("Изменения QSS применены без перезапуска приложения.")
