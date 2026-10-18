#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
School Psychology Testing App - Authentication Window
============================================================
Компонент: Окно входа в систему.
============================================================
"""

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from src.gui.register_window import RegisterWindow
from src.gui.styles.live_reload import load_stylesheet
from src.services.auth_service import AuthService


class AuthWindow(QDialog):
    """Окно авторизации пользователя"""
    
    login_successful = Signal(dict)
    
    def __init__(self, auth_service: AuthService, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self._user_data = None 
        
        self.setWindowTitle("Вход в систему")
        self.setStyleSheet(load_stylesheet())
        self.setup_ui()

    def setup_ui(self):
        """📐 Настройка разметки и дизайна окна"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(50, 40, 50, 50)
        
        # --- БЛОК 1: ПРИВЕТСТВИЕ ---
        header = QVBoxLayout()
        title = QLabel("🏫 Школьный Психолог")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        
        subtitle = QLabel("Система тестирования")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)
        
        layout.addSpacing(25)
        
        # --- БЛОК 2: ЛОГИН ---
        layout.addWidget(QLabel("Логин"))
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Введите ваш логин...")
        self.login_input.setMinimumHeight(45)
        self.login_input.returnPressed.connect(self.login)
        layout.addWidget(self.login_input)
        
        # --- БЛОК 3: ПАРОЛЬ ---
        layout.addWidget(QLabel("Пароль"))
        self.password_input = QLineEdit()
        self.password_input.setObjectName("passwordField")  # Для QSS (padding-right: 35px)
        self.password_input.setPlaceholderText("Введите ваш пароль...")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(45)
        self.password_input.returnPressed.connect(self.login)
        
        # 👁️ Встроенная кнопка переключения видимости
        self.btn_toggle_password = QPushButton("👁️", self.password_input)
        self.btn_toggle_password.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_password.setToolTip("Показать пароль")
        self.btn_toggle_password.setFixedSize(30, 30)
        self.btn_toggle_password.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                font-size: 16px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-radius: 15px;
            }
        """)
        self.btn_toggle_password.clicked.connect(self.toggle_password_visibility)

        # Компоновка внутри поля ввода
        pass_layout = QHBoxLayout(self.password_input)
        pass_layout.setContentsMargins(0, 0, 6, 0)
        pass_layout.addStretch()
        pass_layout.addWidget(self.btn_toggle_password)
        
        layout.addWidget(self.password_input)
        
        layout.addSpacing(15)
        
        # --- БЛОК 4: КНОПКА ВХОДА ---
        self.login_button = QPushButton("Войти в систему")
        self.login_button.setMinimumHeight(50)
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.clicked.connect(self.login)
        layout.addWidget(self.login_button)
        
        # --- БЛОК 5: РЕГИСТРАЦИЯ ---
        reg_layout = QHBoxLayout()
        reg_layout.addStretch()
        
        self.register_button = QPushButton("Создать аккаунт")
        self.register_button.setObjectName("secondary_button")
        self.register_button.setCursor(Qt.PointingHandCursor)
        self.register_button.clicked.connect(self.show_register_window)
        
        reg_layout.addWidget(QLabel("Нет аккаунта?"))
        reg_layout.addWidget(self.register_button)
        reg_layout.addStretch()
        layout.addLayout(reg_layout)
        
        # --- БЛОК 6: СТАТУС ---
        self.status_label = QLabel("")
        self.status_label.setObjectName("status_error")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        self.setFixedSize(480, 580)

    def toggle_password_visibility(self):
        """Метод переключения: Показать/Скрыть текст пароля"""
        if self.password_input.echoMode() == QLineEdit.Password:
            self.password_input.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_password.setText("🔒")
            self.btn_toggle_password.setToolTip("Скрыть пароль")
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
            self.btn_toggle_password.setText("👁️")
            self.btn_toggle_password.setToolTip("Показать пароль")
            
        self.password_input.setFocus()

    def show_register_window(self):
        self.hide()
        reg_win = RegisterWindow(self.auth_service, parent=self)
        if reg_win.exec() == QDialog.Accepted:
            self.status_label.setText("✅ Регистрация успешна! Войдите.")
        self.show()

    @Slot()
    def login(self):
        l_text = self.login_input.text().strip()
        p_text = self.password_input.text().strip()
        if not l_text or not p_text:
            self.status_label.setText("⚠️ Введите данные")
            return
        
        user = self.auth_service.authenticate_user(l_text, p_text)
        if user:
            self._user_data = user
            self.login_successful.emit(user)
            self.accept()
        else:
            self.status_label.setText("❌ Ошибка: неверный логин или пароль")

    def get_user_data(self):
        return self._user_data