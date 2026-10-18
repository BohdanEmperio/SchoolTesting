#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# src/gui/main_window.py

"""
🪟 Главное окно приложения
"""

import logging

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget, QStatusBar

from src.gui.admin.admin_dashboard import AdminDashboard
from src.gui.auth_window import AuthWindow
from src.gui.student.student_dashboard import StudentDashboard
from src.gui.styles.live_reload import load_stylesheet

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    # ✅ ИСПРАВЛЕНО: Теперь конструктор принимает user_data=None
    def __init__(self, auth_service, db_service, user_data=None, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.db_service = db_service
        
        # ✅ Сразу сохраняем переданного пользователя
        self.current_user = user_data
        
        self.setWindowTitle("🏫 Школьный Психолог - Система Тестирования")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(800, 600)
        self.setStyleSheet(load_stylesheet())
        
        # Инициализируем базовые элементы интерфейса
        self.setup_ui()
        
        # ✅ ЛОГИКА: Если мы зашли через main.py (уже есть данные), 
        # то отрисовываем кабинет. Если нет — запускаем вход.
        if self.current_user:
            self.on_login_success(self.current_user)
        else:
            # Сюда попадем только если запускаем MainWindow напрямую
            # без предварительного вызова AuthWindow в main.py
            self.show_auth_window()

    def setup_ui(self):
        """Настройка структуры окна"""
        # Стек виджетов (здесь будут меняться Dashboard-ы в зависимости от роли)
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # Меню и Статус-бар
        self.create_menu_bar()
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Система готова к работе")

    def create_menu_bar(self):
        """Создание верхнего меню"""
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Файл")
        
        logout_action = QAction("🚪 Сменить пользователя", self)
        logout_action.setShortcut("Ctrl+L")
        logout_action.triggered.connect(self.logout)
        file_menu.addAction(logout_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("❌ Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        help_menu = menubar.addMenu("Справка")
        about_action = QAction("ℹ️ О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def on_login_success(self, user_data):
        """Логика загрузки личного кабинета после входа"""
        self.current_user = user_data
        role = user_data.get('role', '')
        logger.info(f"MainWindow: Авторизация роль={role}, student_id={user_data.get('student_id')}")

        # Очищаем старые виджеты из стека (если они были)
        while self.stacked_widget.count() > 0:
            widget = self.stacked_widget.widget(0)
            self.stacked_widget.removeWidget(widget)
        
        # ✅ Определяем кабинет в зависимости от роли
        if role in ['admin', 'psychologist']:
            # Администратор и психолог (используют одну логику панели или разную)
            dashboard = AdminDashboard(self.auth_service, self.db_service, user_data, self)
        elif role == 'student':
            # Кабинет ученика
            dashboard = StudentDashboard(self.auth_service, self.db_service, user_data, self)
        else:
            QMessageBox.critical(self, "Ошибка доступа", "Ваша роль в системе не определена")
            self.show_auth_window()
            return
        
        self.stacked_widget.addWidget(dashboard)
        self.stacked_widget.setCurrentWidget(dashboard)
        
        # Обновляем сообщение внизу
        login_name = user_data.get('login', 'User')
        self.status_bar.showMessage(f"👤 Авторизован: {login_name} | Роль: {role}")

    def show_auth_window(self):
        """Окно входа (если вызывается отдельно)"""
        auth_win = AuthWindow(self.auth_service, self)
        if auth_win.exec() == AuthWindow.Accepted:
            new_data = auth_win.get_user_data()
            self.on_login_success(new_data)
        else:
            # Если вход отменен, а мы еще не залогинены — закрываем все приложение
            if not self.current_user:
                self.close()

    def logout(self):
        """Выход из учетной записи"""
        reply = QMessageBox.question(
            self, 'Выход', 'Вы действительно хотите сменить пользователя?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.current_user = None
            self.status_bar.showMessage("Ожидание входа...")
            self.show_auth_window()

    def show_about(self):
        """Диалог 'О программе'"""
        QMessageBox.about(
            self, "О программе",
            "<h2>🏫 Школьный Психолог</h2>"
            "<p>Профессиональная система психологического тестирования.</p>"
            "<p><b>Версия:</b> 1.0.1 (Стабильная)</p>"
            "<p><b>Школа:</b> МБОУ СОШ №18, г. Братск</p>"
            "<p>© 2026</p>"
        )