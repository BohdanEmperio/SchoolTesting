#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
School Psychology Testing App - Registration Window
============================================================
Компонент: Окно создания учетной записи сотрудника.
Роли: Педагог-психолог, Администратор.
Особенности: Адаптивный размер, поддержка масштабирования экрана.
============================================================
"""

import logging
import re
from typing import Optional

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
from src.services.database_service import DatabaseService

logger = logging.getLogger(__name__)


class RegisterWindow(QDialog):
    """📝 Окно регистрации учетных записей сотрудников с изменяемым размером"""

    def __init__(self, auth_service, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.db_service = DatabaseService()

        self.setWindowTitle("Регистрация сотрудника")
        # Комфортный стартовый размер и снятие блокировки фиксированного окна
        self.resize(580, 680)
        self.setMinimumSize(460, 520)
        self.setStyleSheet(load_stylesheet())

        self.setup_ui()

    def setup_ui(self) -> None:
        """📐 Настройка разметки с поддержкой прокрутки и фиксированными кнопками"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 15, 20, 15)
        root_layout.setSpacing(10)

        # --- 1. ОБЛАСТЬ ПРОКРУТКИ ДЛЯ ФОРМЫ (SCROLL AREA) ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(15, 5, 15, 5)
        content_layout.setSpacing(8)

        # Заголовок
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title_icon = QLabel("📝")
        title_icon.setAlignment(Qt.AlignCenter)
        title_icon.setStyleSheet("font-size: 32px;")

        title_text = QLabel("Регистрация")
        title_text.setObjectName("title")
        title_text.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Создание учетной записи специалиста")
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
            content_layout, "Пароль (мин. 8 символов):*", "Введите пароль...", is_password=True
        )
        self.confirm_input = self._add_input_field(
            content_layout, "Повторите пароль:*", "Повторите пароль...", is_password=True
        )

        # Выбор роли
        self._add_label(content_layout, "Роль в системе:*")
        self.role_combo = QComboBox()
        self.role_combo.addItem("Педагог-психолог", "psychologist")
        self.role_combo.addItem("Администратор", "admin")
        self.role_combo.setMinimumHeight(38)
        content_layout.addWidget(self.role_combo)

        # Информационная плашка для учащихся
        info_banner = QWidget()
        info_banner.setStyleSheet(
            "background-color: #E8F5E9; border-left: 4px solid #4CAF50; "
            "border-radius: 6px; padding: 6px;"
        )
        banner_layout = QVBoxLayout(info_banner)
        banner_layout.setContentsMargins(8, 6, 8, 6)
        lbl_info = QLabel(
            "ℹ️ <b>Учащимся:</b> Создать профиль и учётную запись ученика может "
            "администратор или педагог-психолог в разделе «Ученики»."
        )
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #2E7D32; font-size: 12px; border: none;")
        banner_layout.addWidget(lbl_info)
        content_layout.addWidget(info_banner)

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        root_layout.addWidget(scroll_area)

        # --- 2. НИЖНЯЯ ПАНЕЛЬ С КНОПКАМИ (ВСЕГДА ЗАФИКСИРОВАНА ВНИЗУ) ---
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(15, 0, 15, 0)
        bottom_layout.setSpacing(6)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_register = QPushButton("✅ Зарегистрироваться")
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

        # Статус ошибки
        self.status_label = QLabel("")
        self.status_label.setObjectName("status_error")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        bottom_layout.addWidget(self.status_label)

        root_layout.addWidget(bottom_panel)

    def _add_input_field(
        self, layout: QVBoxLayout, label_text: str, placeholder: str, is_password: bool = False
    ) -> QLineEdit:
        """Вспомогательный метод создания поля ввода с подписью"""
        self._add_label(layout, label_text)
        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)
        input_field.setMinimumHeight(38)
        if is_password:
            input_field.setEchoMode(QLineEdit.Password)
        layout.addWidget(input_field)
        return input_field

    def _add_label(self, layout: QVBoxLayout, text: str) -> None:
        """Вспомогательный метод добавления заголовка к полю"""
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; color: #555; margin-top: 2px;")
        layout.addWidget(lbl)

    def validate_inputs(
        self, login: str, email: Optional[str], password: str, confirm: str
    ) -> Optional[str]:
        """Валидация полей формы перед отправкой в БД"""
        if not re.match(r"^[a-zA-Z0-9_]{3,30}$", login):
            return "Логин должен содержать от 3 до 30 символов (латиница, цифры, '_')"
        if email and not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            return "Неверный формат адреса электронной почты"
        if len(password) < 8:
            return "Пароль должен содержать не менее 8 символов"
        if password != confirm:
            return "Введенные пароли не совпадают"
        return None

    def handle_registration(self) -> None:
        """Процесс сохранения сотрудника в базе данных с валидацией ограничений СУБД"""
        login = self.login_input.text().strip()
        raw_email = self.email_input.text().strip()
        # Если почта не введена, передаем None (SQL NULL), чтобы не нарушать UNIQUE-индекс
        email = raw_email if raw_email else None
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        role = self.role_combo.currentData()

        # 1. Валидация входных данных
        error = self.validate_inputs(login, email, password, confirm)
        if error:
            self.status_label.setText(f"⚠️ {error}")
            return

        self.btn_register.setEnabled(False)
        self.btn_register.setText("⏳ Сохранение...")
        QApplication.processEvents()

        try:
            with self.db_service.get_cursor() as cursor:
                # 2. Проверка уникальности логина
                cursor.execute(
                    "SELECT id FROM psychology.users WHERE login = %s;",
                    (login,)
                )
                if cursor.fetchone():
                    self.status_label.setText("❌ Этот логин уже занят. Выберите другой.")
                    self.btn_register.setEnabled(True)
                    self.btn_register.setText("✅ Зарегистрироваться")
                    return

                # 3. Проверка уникальности email (если он указан)
                if email:
                    cursor.execute(
                        "SELECT id FROM psychology.users WHERE email = %s;",
                        (email,)
                    )
                    if cursor.fetchone():
                        self.status_label.setText("❌ Пользователь с таким Email уже зарегистрирован.")
                        self.btn_register.setEnabled(True)
                        self.btn_register.setText("✅ Зарегистрироваться")
                        return

                # 4. Хеширование пароля через bcrypt
                password_hash = self.auth_service.get_password_hash(password)

                # 5. Запись сотрудника с привязкой к школе по умолчанию
                cursor.execute(
                    """
                    INSERT INTO psychology.users (
                        login,
                        email,
                        password_hash,
                        role,
                        school_id,
                        student_id,
                        is_active,
                        is_verified
                    )
                    VALUES (%s, %s, %s, %s::psychology.user_role, %s, NULL, TRUE, TRUE)
                    RETURNING id;
                    """,
                    (
                        login,
                        email,
                        password_hash,
                        role,
                        DatabaseService.DEFAULT_SCHOOL_ID,
                    ),
                )
                new_user = cursor.fetchone()

                if new_user:
                    logger.info(f"✅ Успешно зарегистрирован сотрудник: {login} (роль: {role})")
                    QMessageBox.information(
                        self,
                        "Регистрация завершена",
                        f"Учетная запись '{login}' успешно создана!\n\n"
                        "Теперь вы можете войти в систему с указанными данными.",
                    )
                    self.accept()

        except Exception as e:
            logger.error(f"Ошибка при регистрации пользователя {login}: {e}", exc_info=True)
            self.status_label.setText(f"❌ Ошибка БД: {str(e)[:50]}")
            self.btn_register.setEnabled(True)
            self.btn_register.setText("✅ Зарегистрироваться")