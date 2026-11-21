#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
School Psychology Testing App - Registration Window
============================================================
Компонент: Окно создания учетной записи сотрудника.
Роли: Педагог-психолог, Администратор.

ЭТАП 1 (14.11.2026). Окно работает в двух режимах:
  • first_run=True  — первичная настройка с экрана входа: в базе ещё нет
                      администратора, можно создать ТОЛЬКО администратора;
  • first_run=False — вызов из панели администратора («Состав» →
                      «Новый аккаунт»): можно создать психолога или админа.
Само окно ничего не решает о правах и не пишет в базу напрямую:
всё делает AuthService.register_staff(), который ещё раз проверяет права.
============================================================
"""

import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles.live_reload import load_stylesheet
from src.services.auth_service import AuthService, RegistrationError

logger = logging.getLogger(__name__)


class RegisterWindow(QDialog):
    """📝 Окно регистрации учетных записей сотрудников"""

    def __init__(
        self,
        auth_service: AuthService,
        parent=None,
        created_by: Optional[Dict[str, Any]] = None,
        first_run: bool = False,
    ):
        super().__init__(parent)
        self.auth_service = auth_service
        # Кто открыл окно (словарь вошедшего пользователя) или None,
        # если окно открыто с экрана входа при первичной настройке.
        self.created_by = created_by
        self.first_run = first_run
        # ⚠️ Раньше здесь было self.db_service = DatabaseService() — второй пул
        # соединений к БД. Теперь окно работает через общий auth_service.

        self.setWindowTitle(
            "Первичная настройка: администратор"
            if first_run
            else "Новая учётная запись сотрудника"
        )
        self.resize(580, 680)
        self.setMinimumSize(460, 520)
        self.setStyleSheet(load_stylesheet())

        self.setup_ui()

    def setup_ui(self) -> None:
        """📐 Разметка: прокручиваемая форма + закреплённые внизу кнопки"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 15, 20, 15)
        root_layout.setSpacing(10)

        # --- 1. ОБЛАСТЬ ПРОКРУТКИ ДЛЯ ФОРМЫ ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 5, 15, 5)
        content_layout.setSpacing(8)

        # Заголовок
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title_icon = QLabel("🛠️" if self.first_run else "📝")
        title_icon.setAlignment(Qt.AlignCenter)
        title_icon.setStyleSheet("font-size: 32px;")

        title_text = QLabel(
            "Первичная настройка" if self.first_run else "Новый сотрудник"
        )
        title_text.setObjectName("title")
        title_text.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Создание первой учётной записи администратора"
            if self.first_run
            else "Создание учётной записи специалиста"
        )
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        header_layout.addWidget(title_icon)
        header_layout.addWidget(title_text)
        header_layout.addWidget(subtitle)
        content_layout.addLayout(header_layout)
        content_layout.addSpacing(6)

        # Поля ввода
        self.login_input = self._add_input_field(
            content_layout, "Логин (латиница и цифры):*", "Придумайте логин..."
        )
        self.email_input = self._add_input_field(
            content_layout, "Электронная почта (необязательно):", "example@school.local"
        )
        self.password_input = self._add_input_field(
            content_layout,
            "Пароль (мин. 8 символов):*",
            "Введите пароль...",
            is_password=True,
        )
        self.confirm_input = self._add_input_field(
            content_layout,
            "Повторите пароль:*",
            "Повторите пароль...",
            is_password=True,
        )

        # Выбор роли.
        # При первичной настройке в списке только «Администратор»: первым
        # обязательно создаётся админ, иначе некому будет управлять системой.
        self._add_label(content_layout, "Роль в системе:*")
        self.role_combo = QComboBox()
        if not self.first_run:
            self.role_combo.addItem("Педагог-психолог", "psychologist")
        self.role_combo.addItem("Администратор", "admin")
        self.role_combo.setMinimumHeight(38)
        self.role_combo.setEnabled(
            not self.first_run
        )  # при первом запуске менять нечего
        content_layout.addWidget(self.role_combo)

        # Информационная плашка
        info_banner = QWidget()
        info_banner.setStyleSheet(
            "background-color: #E8F5E9; border-left: 4px solid #4CAF50; "
            "border-radius: 6px; padding: 6px;"
        )
        banner_layout = QVBoxLayout(info_banner)
        banner_layout.setContentsMargins(8, 6, 8, 6)
        if self.first_run:
            banner_text = (
                "ℹ️ <b>Первый запуск.</b> В системе ещё нет администратора. "
                "После его создания эта кнопка исчезнет с экрана входа, а остальных "
                "сотрудников будет добавлять администратор в разделе «Состав»."
            )
        else:
            banner_text = (
                "ℹ️ <b>Учащимся:</b> профиль и учётную запись ученика создают "
                "в разделе «Ученики»."
            )
        lbl_info = QLabel(banner_text)
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #2E7D32; font-size: 12px; border: none;")
        banner_layout.addWidget(lbl_info)
        content_layout.addWidget(info_banner)

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        root_layout.addWidget(scroll_area)

        # --- 2. НИЖНЯЯ ПАНЕЛЬ С КНОПКАМИ ---
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(15, 0, 15, 0)
        bottom_layout.setSpacing(6)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_register = QPushButton("✅ Создать")
        self.btn_register.setMinimumHeight(44)
        self.btn_register.setCursor(Qt.PointingHandCursor)
        self.btn_register.clicked.connect(self.handle_registration)

        self.btn_cancel = QPushButton("❌ Отмена")
        self.btn_cancel.setMinimumHeight(44)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet("background-color: #f44336; color: white;")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_register)
        btn_layout.addWidget(self.btn_cancel)
        bottom_layout.addLayout(btn_layout)

        # Строка статуса (ошибки)
        self.status_label = QLabel("")
        self.status_label.setObjectName("status_error")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        bottom_layout.addWidget(self.status_label)

        root_layout.addWidget(bottom_panel)

    def _add_input_field(
        self,
        layout: QVBoxLayout,
        label_text: str,
        placeholder: str,
        is_password: bool = False,
    ) -> QLineEdit:
        """Вспомогательный метод: поле ввода с подписью"""
        self._add_label(layout, label_text)
        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setMinimumHeight(38)
        if is_password:
            input_field.setEchoMode(QLineEdit.Password)
        layout.addWidget(input_field)
        return input_field

    def _add_label(self, layout: QVBoxLayout, text: str) -> None:
        """Вспомогательный метод: подпись к полю"""
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; color: #555; margin-top: 2px;")
        layout.addWidget(lbl)

    def _set_busy(self, busy: bool) -> None:
        """Блокирует кнопку на время сохранения, чтобы не создать запись дважды."""
        self.btn_register.setEnabled(not busy)
        self.btn_register.setText("⏳ Сохранение..." if busy else "✅ Создать")

    def handle_registration(self) -> None:
        """Сбор полей формы и передача в AuthService.register_staff()."""
        login = self.login_input.text().strip()
        email = self.email_input.text().strip() or None
        # Пароль НЕ обрезаем: пробелы в пароле — часть пароля.
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        role = self.role_combo.currentData()

        # 1. Быстрая проверка формата прямо в окне (без обращения к БД).
        #    Та же функция ещё раз вызывается внутри register_staff().
        error = AuthService.validate_staff_input(login, email, password, confirm)
        if error:
            self.status_label.setText(f"⚠️ {error}")
            return

        self._set_busy(True)
        QApplication.processEvents()  # чтобы надпись «Сохранение...» успела отрисоваться

        try:
            # 2. Всё остальное — права, уникальность, запись — в сервисе.
            self.auth_service.register_staff(
                login=login,
                email=email,
                password=password,
                confirm=confirm,
                role=role,
                created_by=self.created_by,
            )
        except RegistrationError as e:
            # Ожидаемая ошибка (логин занят, нет прав и т.п.) — показываем как есть.
            self.status_label.setText(f"❌ {e}")
            self._set_busy(False)
            return
        except Exception as e:
            # Неожиданная ошибка (например, нет связи с БД) — подробности в лог.
            logger.error(f"Ошибка при создании сотрудника {login}: {e}", exc_info=True)
            self.status_label.setText(
                "❌ Ошибка базы данных. Подробности в журнале app.log."
            )
            self._set_busy(False)
            return

        QMessageBox.information(
            self,
            "Учётная запись создана",
            f"Учётная запись «{login}» создана.\n\n"
            + (
                "Теперь войдите в систему с указанными данными."
                if self.first_run
                else "Сотрудник может войти в систему с указанными данными."
            ),
        )
        self.accept()
