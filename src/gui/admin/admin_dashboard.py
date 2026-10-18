#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
School Psychology Testing App - Admin Dashboard V5.1
============================================================
Разработчик: AI Assistant & Bogdan
Дата изменения: 2026-04-06
Функционал: Полное управление школьной инфраструктурой
============================================================
"""

import json  # Нужно добавить в импорты в начале файла!
import logging
import math
import random
import re
import string
import traceback
import uuid
from datetime import datetime

import pandas as pd
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles.live_reload import load_stylesheet
from src.gui.admin.question_editor_dialog import QuestionEditorDialog
from src.services.classes_service import ClassesService
from src.services.students_service import StudentsService
from src.services.users_service import UsersService

# Настройка логирования для отладки
logger = logging.getLogger(__name__)


class AdminDashboard(QWidget):
    """
    Основной класс панели администратора. 
    Отвечает за отрисовку всех вкладок управления.
    """

    def __init__(self, auth_service, db_service, user_data, parent=None):
        super().__init__(parent)
        
        # Инициализация сервисов
        self.auth_service = auth_service
        self.db_service = db_service
        self.classes_service = ClassesService(db_service)
        self.students_service = StudentsService(db_service)
        self.users_service = UsersService(db_service)
        self.user_data = user_data

        # Инициализация ссылок на UI элементы (таблицы и фильтры)
        self.users_table = None
        self.classes_table = None
        self.students_table = None
        #self.results_table = None
        self.tests_table = None
        self.student_class_filter = None
        

        # Применение стилей QSS
        self.setStyleSheet(load_stylesheet())
        
        # Построение интерфейса
        self.setup_ui()

    def setup_ui(self):
        """📏 Конструктор разметки главного экрана администратора"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- ВЕРХНИЙ БЛОК (ШАПКА) ---
        role = self.user_data.get("role", "admin")
        title_text = "👤 Панель Администратора" if role == "admin" else "⚕️ Панель Психолога"

       # --- ВЕРХНИЙ КОНТЕЙНЕР (HEADER) ---
        header_container = QHBoxLayout()
        header_label = QLabel(title_text)
        header_label.setObjectName("title")
        header_container.addWidget(header_label)
        
        header_container.addStretch()

        # Мы сделаем её с Badge-эффектом (текстом о количестве непрочитанных)
        self.notif_btn = QPushButton("🔔 Оповещения (0)")
        self.notif_btn.setMinimumHeight(45)
        self.notif_btn.setMinimumWidth(180)
        self.notif_btn.setCursor(Qt.PointingHandCursor)
        # Окрасим её в синий, чтобы отличалась от зеленой синхронизации
        self.notif_btn.setStyleSheet("background-color: #3F51B5; color: white; font-weight: bold;")
        self.notif_btn.clicked.connect(self.show_notifications_center)
        header_container.addWidget(self.notif_btn)

        # Кнопка быстрой синхронизации
        sync_button = QPushButton("🔄 Синхронизировать БД")
        sync_button.setMinimumHeight(45)
        sync_button.setMinimumWidth(220)
        sync_button.setCursor(Qt.PointingHandCursor)
        sync_button.clicked.connect(self.manual_refresh_all)
        header_container.addWidget(sync_button)

        layout.addLayout(header_container)
        
        # --- ОСНОВНОЙ ВИДЖЕТ ПЕРЕКЛЮЧЕНИЯ ВКЛАДОК ---
        self.tabs = QTabWidget()
        self.tabs.setObjectName("adminMainTabs")

        # 1. Вкладка статистики и сводки
        self.tabs.addTab(self.create_main_tab(), "📊 Сводка")
        
        # 2. Вкладка управления персоналом/аккаунтами
        self.tabs.addTab(self.create_users_tab(), "👥 Состав")
        
        # 3. Вкладка учебных групп (Классы)
        self.tabs.addTab(self.create_classes_tab(), "📚 Классы")
        
        # 4. Вкладка учащихся (Список и Excel импорт)
        self.tabs.addTab(self.create_students_tab(), "🎓 Ученики")
        
        # 5. Вкладка архива завершенных тестов
        self.tabs.addTab(self.create_results_tab(), "🏆 Результаты")
        
        # 6. Вкладка редактора психологических методик
        self.tabs.addTab(self.create_tests_tab(), "📝 Тесты")
        
        # 7. Вкладка информации об организации
        self.tabs.addTab(self.create_schools_tab(), "🏫 Школа")
        
        # 8. Вкладка системных сервисов
        self.tabs.addTab(self.create_settings_tab(), "⚙️ Опции")

        layout.addWidget(self.tabs)
        self.setLayout(layout)
        self.update_notif_counter()


    # ============================================================
    # 📊 ВКЛАДКА 0: ГЛАВНАЯ (ВИЗУАЛИЗАЦИЯ ДАННЫХ)
    # ============================================================
    def create_main_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(15, 15, 15, 15)

        welcome_text = f"Добро пожаловать, {self.user_data.get('login', 'User')}!"
        welcome_label = QLabel(welcome_text)
        welcome_label.setObjectName("subtitle")
        layout.addWidget(welcome_label)

        layout.addSpacing(10)

        # Секция с карточками показателей
        cards_layout = QHBoxLayout()
        
        # Прямое получение статистики через SQL-подзапросы для точности
        u_cnt = c_cnt = s_cnt = "?"
        try:
            with self.db_service.get_cursor() as cursor:
                query = """
                    SELECT 
                        (SELECT COUNT(*) FROM psychology.users),
                        (SELECT COUNT(*) FROM psychology.classes WHERE is_active = TRUE),
                        (SELECT COUNT(*) FROM psychology.students WHERE is_active = TRUE)
                """
                cursor.execute(query)
                res = cursor.fetchone()
                if res:
                    u_cnt, c_cnt, s_cnt = res
        except Exception as e:
            logger.error(f"Failed to fetch dashboard stats: {e}")

        # Список кортежей (Название, Значение, Цвет нижней рамки)
        statistics = [
            ("👤 Пользователи", str(u_cnt), "#2196F3"),
            ("📚 Учебные группы", str(c_cnt), "#4CAF50"),
            ("🎓 Ученики в базе", str(s_cnt), "#FF9800"),
            ("🧪 Диагностики", "2", "#9C27B0")
        ]

        for title, value, color in statistics:
            card = QWidget()
            card.setMinimumHeight(150)
            card.setStyleSheet(f"""
                QWidget {{
                    background: white;
                    border: 1px solid #dee2e6;
                    border-bottom: 6px solid {color};
                    border-radius: 12px;
                }}
            """)
            card_layout = QVBoxLayout(card)
            
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("color: #666; font-size: 13px; font-weight: bold; border: none;")
            
            val_lbl = QLabel(value)
            val_lbl.setAlignment(Qt.AlignCenter)
            val_lbl.setStyleSheet("font-size: 38px; font-weight: 800; color: #333; border: none; margin-top: 5px;")
            
            card_layout.addWidget(title_lbl)
            card_layout.addWidget(val_lbl)
            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)
        
        layout.addSpacing(35)
        
        # Системное уведомление
        notification = QWidget()
        notification.setStyleSheet("background: #f8f9fa; border-left: 5px solid #28a745; padding: 20px; border-radius: 4px;")
        notif_layout = QVBoxLayout(notification)
        notif_layout.addWidget(QLabel("💎 <b>Централизованная система безопасности V4.0</b>"))
        notif_layout.addWidget(QLabel("Все действия сотрудников в панели логируются. В системе активен режим шифрования данных."))
        layout.addWidget(notification)

        layout.addStretch()
        return page

    # ============================================================
    # 👥 ВКЛАДКА 1: УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
    # ============================================================
    def create_users_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.users_table = QTableWidget(0, 4)
        header_labels = ["Идентификатор", "Имя пользователя", "Роль доступа", "Статус аккаунта"]
        self.users_table.setHorizontalHeaderLabels(header_labels)
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)

        layout.addWidget(self.users_table)
        self.refresh_users_table()

        # Панель кнопок управления персоналом
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        # 1. Создание аккаунта (вызывает модальное окно регистрации)
        add_user_btn = QPushButton("➕ Новый аккаунт")
        add_user_btn.setMinimumHeight(45)
        add_user_btn.setCursor(Qt.PointingHandCursor)
        add_user_btn.clicked.connect(self.on_add_user_clicked)
        action_layout.addWidget(add_user_btn)

        # 2. Переключение блокировки
        self.btn_toggle_user = QPushButton("🔒 Заблокировать / Активировать")
        self.btn_toggle_user.setMinimumHeight(45)
        self.btn_toggle_user.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_user.setStyleSheet(
            "background-color: #FF9800; color: white; font-weight: bold; border-radius: 6px;"
        )
        self.btn_toggle_user.clicked.connect(self.on_toggle_user_status_clicked)
        action_layout.addWidget(self.btn_toggle_user)

        # 3. Удаление аккаунта
        self.btn_delete_user = QPushButton("🗑️ Удалить пользователя")
        self.btn_delete_user.setMinimumHeight(45)
        self.btn_delete_user.setCursor(Qt.PointingHandCursor)
        self.btn_delete_user.setObjectName("cancelButton")
        self.btn_delete_user.clicked.connect(self.on_delete_user_clicked)
        action_layout.addWidget(self.btn_delete_user)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        return page



    

    def refresh_users_table(self):
        """
        🚀 Профессиональная синхронизация таблицы сотрудников и пользователей.
        Реализована Senior-логика форматирования данных и защиты интерфейса.
        """
        if not self.users_table:
            return

        # Отключаем визуальное обновление для предотвращения мерцания при массовой вставке
        self.users_table.setUpdatesEnabled(False)
        self.users_table.setRowCount(0)
        
        try:
            data = self.users_service.get_all_users()
                
            for r_idx, row in enumerate(data):
                self.users_table.insertRow(r_idx)
                
                for c_idx, val in enumerate(row):
                    # --- ЛОГИКА ТЕКСТОВОГО ОТОБРАЖЕНИЯ ---
                    if c_idx == 2:
                        # Красиво форматируем роль: 'student' -> '🎓 Student'
                        display_text = str(val).capitalize()
                    elif c_idx == 3:
                        # Инфографика статуса
                        display_text = "✅ Активен" if val else "🚫 Заблокирован"
                    else:
                        display_text = str(val)

                    # --- СОЗДАНИЕ ЭЛЕМЕНТА ЯЧЕЙКИ ---
                    item = QTableWidgetItem(display_text)
                    
                    # Блокировка редактирования ячейки пользователем (Senior Standard)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

                    # Выравнивание иконки статуса по центру
                    if c_idx == 3:
                        item.setTextAlignment(Qt.AlignCenter)
                    
                    # Если аккаунт заблокирован, подкрашиваем строку серым цветом
                    if not row[3]:
                        item.setForeground(Qt.gray)

                    self.users_table.setItem(r_idx, c_idx, item)

            logger.info(f"Синхронизировано пользователей в таблице: {len(data)}")

        except Exception as e:
            logger.error(f"❌ Ошибка рендеринга списка пользователей: {e}")
            # QMessageBox тут не используем, чтобы не спамить при фоновых обновлениях
        
        finally:
            # Включаем прорисовку обратно
            self.users_table.setUpdatesEnabled(True)



    @Slot()
    def on_add_user_clicked(self):
        """Открытие формы регистрации нового сотрудника прямо из панели администратора"""
        from src.gui.register_window import RegisterWindow
        dialog = RegisterWindow(self.auth_service, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh_users_table()
            self.manual_refresh_all()

    @Slot()
    def on_toggle_user_status_clicked(self):
        """Слот блокировки / разблокировки выбранного пользователя"""
        row = self.users_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Выбор не сделан", "Пожалуйста, выделите строку с пользователем в таблице.")
            return

        target_user_id = self.users_table.item(row, 0).text()
        target_login = self.users_table.item(row, 1).text()
        status_text = self.users_table.item(row, 3).text()

        # 🛡️ Защита от дурака: нельзя заблокировать свой собственный текущий сеанс
        current_user_id = str(self.user_data.get("id"))
        if target_user_id == current_user_id:
            QMessageBox.warning(
                self, 
                "Защита доступа", 
                "Вы не можете заблокировать свой собственный текущий аккаунт!"
            )
            return

        # Инвертируем текущий статус
        is_currently_active = "Активен" in status_text
        new_status = not is_currently_active
        action_word = "заблокировать" if is_currently_active else "активировать"

        confirm = QMessageBox.question(
            self,
            "Подтверждение действия",
            f"Вы уверены, что хотите {action_word} учетную запись <b>{target_login}</b>?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            self.users_service.toggle_user_active(target_user_id, new_status)
            self.refresh_users_table()
            status_desc = "активирован" if new_status else "заблокирован"
            QMessageBox.information(
                self, 
                "Готово", 
                f"Статус аккаунта '{target_login}' успешно изменен: {status_desc}."
            )
        except Exception as e:
            logger.error(f"Failed to toggle user status: {e}")
            QMessageBox.critical(self, "Ошибка БД", f"Не удалось изменить статус пользователя:\n{e}")

    @Slot()
    def on_delete_user_clicked(self):
        """Слот физического удаления выбранного пользователя"""
        row = self.users_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Выбор не сделан", "Пожалуйста, выделите строку с пользователем в таблице.")
            return

        target_user_id = self.users_table.item(row, 0).text()
        target_login = self.users_table.item(row, 1).text()
        target_role = self.users_table.item(row, 2).text()

        # 🛡️ Защита от дурака: нельзя удалить самого себя
        current_user_id = str(self.user_data.get("id"))
        if target_user_id == current_user_id:
            QMessageBox.warning(
                self, 
                "Защита доступа", 
                "Вы не можете удалить свой собственный текущий аккаунт!"
            )
            return

        confirm = QMessageBox.question(
            self,
            "⚠️ Подтверждение удаления",
            f"Вы действительно хотите навсегда удалить пользователя <b>{target_login}</b> (роль: {target_role})?<br><br>"
            "<b>Внимание:</b> Это действие необратимо!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            self.users_service.delete_user(target_user_id)
            self.refresh_users_table()
            self.manual_refresh_all()
            QMessageBox.information(
                self, 
                "Успех", 
                f"Учетная запись '{target_login}' была успешно удалена из системы."
            )
        except Exception as e:
            logger.error(f"Failed to delete user: {e}")
            QMessageBox.critical(self, "Ошибка БД", f"Не удалось удалить пользователя:\n{e}")


    # ============================================================
    # 📚 ВКЛАДКА 2: УПРАВЛЕНИЕ КЛАССАМИ (ГРУППАМИ)
    # ============================================================
    def create_classes_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        instruction = QLabel("📚 Для просмотра учеников определенного класса нажмите на строку дважды.")
        instruction.setStyleSheet("color: #777; margin-bottom: 5px; font-style: italic;")
        layout.addWidget(instruction)

        self.classes_table = QTableWidget(0, 4)
        labels = ["Системный ID", "Название", "Параллель/Уровень", "Учеников в группе"]
        self.classes_table.setHorizontalHeaderLabels(labels)
        self.classes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.classes_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # РЕАЛИЗАЦИЯ ФИШКИ: Переход при двойном клике
        self.classes_table.cellDoubleClicked.connect(self.on_class_double_clicked)

        layout.addWidget(self.classes_table)
        self.refresh_classes_table()

        btn_row = QHBoxLayout()
        btn_add = QPushButton("➕ Добавить класс")
        btn_edit = QPushButton("✏️ Переименовать")
        btn_del = QPushButton("🗑️ Расформировать")
        btn_del.setObjectName("cancelButton") # Цвет кнопки задается в qss

        for b, method in [(btn_add, self.on_add_class_clicked), 
                          (btn_edit, self.on_edit_class_clicked), 
                          (btn_del, self.on_delete_class_clicked)]:
            b.setMinimumHeight(48)
            b.clicked.connect(method)
            btn_row.addWidget(b)

        layout.addLayout(btn_row)
        return page

    def refresh_classes_table(self):
        """Загрузка групп и актуальное количество людей."""
        if not self.classes_table:
            return
        self.classes_table.setRowCount(0)
        try:
            data = self.classes_service.get_all_classes()
            for r_idx, row_data in enumerate(data):
                self.classes_table.insertRow(r_idx)
                for col_idx, val in enumerate(row_data):
                    item = QTableWidgetItem(str(val))
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.classes_table.setItem(r_idx, col_idx, item)
        except Exception as e:
            logger.error(f"Refresh classes table failed: {e}")

    #
    # ============================================================
    # 🎓 ВКЛАДКА 3: УЧЕНИКИ (ОБНОВЛЕННАЯ С КНОПКАМИ ДОСТУПА)
    # ============================================================
    def create_students_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        # 1. Тулбар (Фильтр и Поиск)
        tools = QHBoxLayout()
        tools.addWidget(QLabel("🗂️ Группа:"))
        self.student_class_filter = QComboBox()
        self.student_class_filter.setMinimumWidth(220)
        self.student_class_filter.currentIndexChanged.connect(self.refresh_students_table)
        tools.addWidget(self.student_class_filter)
        
        tools.addSpacing(20)
        tools.addWidget(QLabel("🔍 Поиск:"))
        self.student_search_input = QLineEdit()
        self.student_search_input.setPlaceholderText("Введите Фамилию для поиска...")
        self.student_search_input.textChanged.connect(self.refresh_students_table)
        tools.addWidget(self.student_search_input)
        
        tools.addStretch()
        layout.addLayout(tools)

        # 2. Таблица
        self.students_table = QTableWidget(0, 8)
        self.students_table.setHorizontalHeaderLabels(["ID", "Код", "Фамилия", "Имя", "Отчество", "Дата рождения", "Пол", "Класс"])
        self.students_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.students_table.setSelectionMode(QTableWidget.ExtendedSelection) # Чтобы выделять многих учеников
        self.students_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.students_table)

        # 3. ПАНЕЛЬ КНОПОК (ПРОВЕРЬ ЭТОТ СПИСОК!)
        btns_layout = QHBoxLayout()
        
        # Список кнопок: (Текст, Слот-обработчик, Специальный стиль)
        student_actions = [
            ("➕ Регистрация", self.on_add_student_clicked, None),
            ("📋 Согласие 152-ФЗ", self.on_bulk_consent_clicked, "background-color: #009688; color: white; font-weight: bold;"),
            ("📥 Импорт Excel", self.on_import_excel_clicked, "background-color: #2196F3; color: white;"),
            ("✏️ Профиль", self.on_edit_student_clicked, None),
            ("🗑️ Удалить", self.on_delete_student_clicked, "cancelButton"),
            # ✨ ВОТ ЭТИ КНОПКИ ТЫ ИЩЕШЬ:
            ("🔐 Открыть доступ", self.on_manage_access_clicked, "background-color: #FF9800; color: white; font-weight: bold;"),
            ("🚫 Закрыть доступ", self.on_revoke_access_clicked, "background-color: #f44336; color: white;")
        ]

        for text, slot, style in student_actions:
            btn = QPushButton(text)
            btn.setMinimumHeight(50)
            btn.clicked.connect(slot) # Подключаем к логике
            
            if style == "cancelButton":
                btn.setObjectName("cancelButton")
            elif style:
                btn.setStyleSheet(style)
                
            btns_layout.addWidget(btn)

        layout.addLayout(btns_layout)

        # Подгрузка данных
        self.refresh_filter_combo()
        self.refresh_students_table()
        
        return page
    
    # ============================================================
    # 🏆 ВКЛАДКА 4: РЕЗУЛЬТАТЫ (ПРОТОКОЛЫ)
    # ============================================================
    def create_results_tab(self):
        """Создание таблицы с результатами пройденных тестов."""
        page = QWidget()
        layout = QVBoxLayout(page)
        
        header = QLabel("📊 Протоколы завершенных тестов")
        header.setObjectName("subtitle") # Используем стандартный стиль подзаголовка
        layout.addWidget(header)

        # 1. Инициализация таблицы
        self.results_table = QTableWidget(0, 6)
        headers = ["ID (Session)", "Код ученика", "Методика", "Общий балл", "Уровень риска", "Дата прохождения"]
        self.results_table.setHorizontalHeaderLabels(headers)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows) # Выделение строками
        
        layout.addWidget(self.results_table)
        
        # 2. ПАНЕЛЬ КНОПОК (Горизонтальная)
        # Senior подход: группируем кнопки управления в один ряд
        action_layout = QHBoxLayout()
        
        # Кнопка ОБНОВЛЕНИЯ
        refresh_results_btn = QPushButton("🔄 Обновить список")
        refresh_results_btn.setMinimumHeight(45)
        refresh_results_btn.clicked.connect(self.refresh_results_table)
        
        # Кнопка ЭКСПОРТА (Word)
        self.btn_export_doc = QPushButton("📄 Скачать отчет (Word)")
        self.btn_export_doc.setMinimumHeight(45)
        # Настройка стиля (Фиолетовая как в инструкции)
        self.btn_export_doc.setStyleSheet("""
            QPushButton {
                background-color: #673AB7; 
                color: white; 
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #5E35B1; }
        """)
        self.btn_export_doc.setCursor(Qt.PointingHandCursor)
        self.btn_export_doc.clicked.connect(self.on_export_report_clicked)

        # Добавляем кнопки в горизонтальный ряд
        action_layout.addWidget(refresh_results_btn)
        action_layout.addWidget(self.btn_export_doc)
        action_layout.addStretch() # Прижимаем кнопки к левому краю
        
        # Добавляем ряд кнопок в основной вертикальный макет страницы
        layout.addLayout(action_layout)

        # Первичная загрузка данных
        self.refresh_results_table()
        
        return page

    def refresh_results_table(self):
        """Загрузка и отрисовка протоколов тестирования в таблицу результатов"""
        if not self.results_table: 
            return
            
        # Полностью очищаем таблицу перед заливкой новых данных
        self.results_table.setRowCount(0)
        
        try:
            # Получаем сводные данные: (id_результата, код_ученика, название_теста, балл, риск, дата)
            results = self.db_service.get_test_results()
            
            for row_idx, row_data in enumerate(results):
                # ✅ ИСПРАВЛЕНО: Теперь вставляем именно в results_table, а не в students_table
                self.results_table.insertRow(row_idx)
                
                # СТАЛО:
                for col_idx, value in enumerate(row_data):
                    # Колонка 5 — это дата: форматируем в аккуратный вид "ДД.ММ.ГГГГ ЧЧ:ММ"
                    if col_idx == 5 and hasattr(value, 'strftime'):
                        display_text = value.strftime("%d.%m.%Y %H:%M")
                    else:
                        display_text = str(value) if value is not None else "---"

                    item = QTableWidgetItem(display_text)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

                    # Выравниваем дату, балл и ID по центру
                    if col_idx in (0, 1, 3, 4, 5):
                        item.setTextAlignment(Qt.AlignCenter)

                    self.results_table.setItem(row_idx, col_idx, item)
                    
        except Exception as e:
            logger.error(f"Ошибка рендеринга таблицы результатов: {e}")
            # Для отладки можно вывести подробности в консоль
            import traceback
            traceback.print_exc()

    # ============================================================
    # 📝 ВКЛАДКА 5: ТЕСТЫ (МЕТОДИКИ)
    # ============================================================
    def create_tests_tab(self):
        
        page = QWidget()
        layout = QVBoxLayout(page)

        self.tests_table = QTableWidget(0, 4)
        # Убедись, что заголовки соответствуют ID, Код, Название, Вопросы
        self.tests_table.setHorizontalHeaderLabels(["ID", "Код", "Название", "Вопросов (ед.)"])
        self.tests_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tests_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.tests_table)
        self.refresh_tests_table()

        t_btns = QHBoxLayout()
        
        # Кнопка создания
        b_add_t = QPushButton("➕ Создать методику")
        b_add_t.setMinimumHeight(45)
        b_add_t.clicked.connect(self.on_add_test_clicked)
        
        # ✨ НОВАЯ КНОПКА: Редактирование
        b_edit_t = QPushButton("✏️ Редактировать")
        b_edit_t.setMinimumHeight(45)
        b_edit_t.clicked.connect(self.on_edit_test_clicked) # Привязываем новый метод
        
        # Кнопка удаления
        b_del_t = QPushButton("🗑️ Удалить методику")
        b_del_t.setMinimumHeight(45)
        b_del_t.setObjectName("cancelButton")
        b_del_t.clicked.connect(self.on_delete_test_clicked)
        
        t_btns.addWidget(b_add_t)
        t_btns.addWidget(b_edit_t) # Добавляем на панель
        t_btns.addWidget(b_del_t)
        layout.addLayout(t_btns)
        
        # Рядом с "Создать методику"
        btn_import_test = QPushButton("📥 Импорт Методики (Excel)")
        btn_import_test.clicked.connect(self.on_import_test_structure)
        btn_import_test.setStyleSheet("background-color: #9C27B0; color: white;")
        t_btns.addWidget(btn_import_test)
        
        
        btn_ai_import = QPushButton("🧠 AI Импорт (PDF)")
        btn_ai_import.setMinimumHeight(45)
        btn_ai_import.setStyleSheet("background-color: #E91E63; color: white; font-weight: bold;")
        btn_ai_import.clicked.connect(self.on_ai_import_pdf)
        t_btns.addWidget(btn_ai_import)
        
        return page
        
    def refresh_tests_table(self):
        """Актуализация каталога тестов."""
        if not self.tests_table:
            return
        self.tests_table.setRowCount(0)
        try:
            for row_idx, row in enumerate(self.db_service.get_all_tests()):
                self.tests_table.insertRow(row_idx)
                # row: (id, code, name, questions_count)
                for c_idx, v in enumerate(row):
                    self.tests_table.setItem(row_idx, c_idx, QTableWidgetItem(str(v)))
        except Exception as e:
            logger.error(f"Tests tab failed refresh: {e}")


    def on_import_test_structure(self):
        """Загрузка полной структуры теста из Excel (два листа: Вопросы и Шкалы)"""
        import pandas as pd  # ✨ ДОБАВИТЬ СЮДА (локальный импорт)
        from PySide6.QtWidgets import QFileDialog
       
       
        path, _ = QFileDialog.getOpenFileName(self, "Методика Excel", "", "Excel (*.xlsx)")
        if not path: 
            return

        try:
            # Читаем основные данные (из имени файла или первой строки)
            t_name = path.split('/')[-1].replace('.xlsx', '')
            t_code = t_name.upper()[:10]

            # Читаем лист вопросов: [Текст, Ответ_Да, Ответ_Нет]
            df_q = pd.read_excel(path, sheet_name=0)
            questions = []
            for i, row in df_q.iterrows():
                # Формируем JSON весов ответов
                opts = {"Да": row.get('Да', 1), "Нет": row.get('Нет', 0)}
                questions.append({
                    'order': i + 1,
                    'text': str(row.get('Текст', '???')),
                    'options': json.dumps(opts, ensure_ascii=False)
                })

            # Читаем лист шкал: [Название, Номера_Вопросов, Coef, Min, Max, Текст]
            df_s = pd.read_excel(path, sheet_name=1)
            scales = []
            for _, row in df_s.iterrows():
                scales.append({
                    'name': str(row['Название']),
                    'mapping': str(row['Номера_Вопросов']), # Напр: "1,12,14"
                    'coef': float(row.get('Coef', 1.0)),
                    'min': int(row.get('Min', 0)),
                    'max': int(row.get('Max', 10)),
                    'interpretation': str(row.get('Текст', ''))
                })

            test_info = {'code': t_code, 'name': t_name, 'desc': 'Импортированная методика'}
            self.db_service.save_complex_test(test_info, questions, scales)
            
            QMessageBox.information(self, "Успех", f"Методика '{t_name}' успешно импортирована!")
            self.refresh_tests_table()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка импорта", f"Некорректный файл методики:\n{str(e)}")



    def on_ai_import_pdf(self):
        """Логика автоматического распознавания PDF методички тестов."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбор методички PDF", "", "PDF Files (*.pdf)"
        )
        if not path:
            return

        # Удалили переменную progress =, вызываем метод напрямую
        QMessageBox.information(
            self, 
            "AI Обработка", 
            "Система приступает к анализу документа.\nПроцесс может занять несколько секунд."
        )
        
        try:
            # 1. Запуск парсера в DatabaseService
            test_data = self.db_service.parse_pdf_methodology(path)
            
            if not test_data.get('questions'):
                raise ValueError("В файле не найдено пронумерованных вопросов (1. ... 2. ...).")

            # 2. Формируем заголовочные данные теста
            test_info = {
                'code': "AI_PDF_" + uuid.uuid4().hex[:4].upper(),
                'name': test_data['name'],
                'desc': test_data['description'], # Из новых ключей парсера
                'instructions': test_data['instructions'] # Из новых ключей парсера
            }
            
            # 3. Сохраняем в базу (структуру тестов мы писали ранее)
            self.db_service.save_complex_test(
                test_info, 
                test_data['questions'], 
                test_data['scales']
            )
            
            # 4. Итоговое уведомление
            count_q = len(test_data['questions'])
            count_s = len(test_data['scales'])
            
            QMessageBox.information(
                self, 
                "Успех", 
                f"Тест успешно считан и добавлен в базу!\n\n"
                f"Название: {test_info['name']}\n"
                f"Вопросов: {count_q}\n"
                f"Шкал оценки: {count_s}\n\n"
                "Рекомендуется проверить веса ответов через кнопку 'Редактировать'."
            )
            
            self.refresh_tests_table()
            self.manual_refresh_all()

        except Exception as err:
            logger.error(f"Critical AI PDF Import fail: {err}")
            traceback.print_exc()
            QMessageBox.critical(
                self, 
                "Ошибка AI импорта", 
                f"Не удалось распознать документ автоматически.\n\n"
                f"Причина: {str(err)}\n\n"
                "Убедитесь, что PDF содержит текстовый слой (не является картинкой)."
            )
            
    # ============================================================
    # 🏫 ШКОЛА И ⚙️ НАСТРОЙКИ (ФУНКЦИИ В КАРТОЧКАХ)
    # ============================================================
    def create_schools_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        box = QWidget()
        box.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 15px; padding: 30px;")
        f_lay = QFormLayout(box)
        f_lay.setSpacing(15)

        lbl_nm = QLabel("МБОУ СОШ №18")
        lbl_adr = QLabel("Иркутская область, г. Братск")
        lbl_ph = QLabel("+7 (3953) 00-00-00")
        
        f_lay.addRow("🏫 Учреждение:", lbl_nm)
        f_lay.addRow("📍 Адрес фактический:", lbl_adr)
        f_lay.addRow("📞 Контактный номер:", lbl_ph)

        layout.addWidget(box)
        layout.addStretch()
        return page

    # ============================================================
    # ⚙️ ВКЛАДКА 7: НАСТРОЙКИ, БЭКАПЫ И АУДИТ 152-ФЗ (V13.0)
    # ============================================================
    def create_settings_tab(self):
        """Создание обновленного центра управления системой и безопасностью."""
        from PySide6.QtWidgets import QFrame, QScrollArea
        from config.settings import settings

        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(15, 15, 15, 15)

        # Оборачиваем в ScrollArea для гарантии работы на экранах любых ноутбуков
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(18)
        layout.setContentsMargins(5, 5, 5, 5)

        # Общий QSS-стиль для карточек опций (исключает слияние текста с фоном)
        card_qss = """
            QFrame#optionsCard {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
            }
        """

        # ------------------------------------------------------------
        # КАРТОЧКА 1: Резервное копирование БД
        # ------------------------------------------------------------
        card_backup = QFrame()
        card_backup.setObjectName("optionsCard")
        card_backup.setStyleSheet(card_qss)
        lay_b = QVBoxLayout(card_backup)
        lay_b.setSpacing(10)

        lbl_b_title = QLabel("💾 Резервное копирование базы данных (Backup)")
        lbl_b_title.setStyleSheet("font-weight: bold; font-size: 15px; color: #2E7D32;")
        lbl_b_desc = QLabel("Создание независимого SQL-дампа всех таблиц и персональных данных учащихся.")
        lbl_b_desc.setStyleSheet("color: #666; font-size: 13px;")

        self.lbl_backup_status = QLabel("Статус последней копии: загрузка...")
        self.lbl_backup_status.setStyleSheet("color: #444; font-size: 13px; font-style: italic;")

        btn_row_b = QHBoxLayout()
        btn_row_b.setSpacing(12)

        self.btn_run_backup = QPushButton("💾 Создать резервную копию (.sql)")
        self.btn_run_backup.setMinimumHeight(45)
        self.btn_run_backup.setCursor(Qt.PointingHandCursor)
        self.btn_run_backup.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; border-radius: 6px; padding: 0 15px;")
        self.btn_run_backup.clicked.connect(self.on_create_backup_clicked)

        self.btn_open_backup_folder = QPushButton("📁 Открыть папку с копиями")
        self.btn_open_backup_folder.setMinimumHeight(45)
        self.btn_open_backup_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_backup_folder.setStyleSheet("background-color: #607D8B; color: white; font-weight: bold; border-radius: 6px; padding: 0 15px;")
        self.btn_open_backup_folder.clicked.connect(self.on_open_backup_folder_clicked)

        btn_row_b.addWidget(self.btn_run_backup)
        btn_row_b.addWidget(self.btn_open_backup_folder)
        btn_row_b.addStretch()

        lay_b.addWidget(lbl_b_title)
        lay_b.addWidget(lbl_b_desc)
        lay_b.addWidget(self.lbl_backup_status)
        lay_b.addLayout(btn_row_b)
        layout.addWidget(card_backup)

        # ------------------------------------------------------------
        # КАРТОЧКА 2: Безопасность и аудит (152-ФЗ)
        # ------------------------------------------------------------
        card_security = QFrame()
        card_security.setObjectName("optionsCard")
        card_security.setStyleSheet(card_qss)
        lay_s = QVBoxLayout(card_security)
        lay_s.setSpacing(10)

        lbl_s_title = QLabel("🛡️ Журналы безопасности и доступ к данным (152-ФЗ)")
        lbl_s_title.setStyleSheet("font-weight: bold; font-size: 15px; color: #1565C0;")
        lbl_s_desc = QLabel("Управление журналом аудита операций, просмотр системных логов и учетных данных.")
        lbl_s_desc.setStyleSheet("color: #666; font-size: 13px;")

        btn_row_s = QHBoxLayout()
        btn_row_s.setSpacing(12)

        self.btn_audit_export = QPushButton("📋 Выгрузить журнал аудита (Excel)")
        self.btn_audit_export.setMinimumHeight(45)
        self.btn_audit_export.setCursor(Qt.PointingHandCursor)
        self.btn_audit_export.setStyleSheet("background-color: #673AB7; color: white; font-weight: bold; border-radius: 6px; padding: 0 15px;")
        self.btn_audit_export.clicked.connect(self.on_export_audit_clicked)

        self.btn_view_logs = QPushButton("📄 Открыть системный журнал (app.log)")
        self.btn_view_logs.setMinimumHeight(45)
        self.btn_view_logs.setCursor(Qt.PointingHandCursor)
        self.btn_view_logs.setStyleSheet("background-color: #455A64; color: white; font-weight: bold; border-radius: 6px; padding: 0 15px;")
        self.btn_view_logs.clicked.connect(self.on_open_app_log_clicked)

        self.btn_change_pwd = QPushButton("🔑 Сменить пароль администратора")
        self.btn_change_pwd.setMinimumHeight(45)
        self.btn_change_pwd.setCursor(Qt.PointingHandCursor)
        self.btn_change_pwd.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; border-radius: 6px; padding: 0 15px;")
        self.btn_change_pwd.clicked.connect(self.on_change_password_clicked)

        btn_row_s.addWidget(self.btn_audit_export)
        btn_row_s.addWidget(self.btn_view_logs)
        btn_row_s.addWidget(self.btn_change_pwd)
        btn_row_s.addStretch()

        lay_s.addWidget(lbl_s_title)
        lay_s.addWidget(lbl_s_desc)
        lay_s.addLayout(btn_row_s)
        layout.addWidget(card_security)

        # ------------------------------------------------------------
        # КАРТОЧКА 3: Системная диагностика и параметры инстанса
        # ------------------------------------------------------------
        card_info = QFrame()
        card_info.setObjectName("optionsCard")
        card_info.setStyleSheet(card_qss)
        lay_i = QVBoxLayout(card_info)
        lay_i.setSpacing(10)

        lbl_i_title = QLabel("⚙️ Параметры системы и окружения")
        lbl_i_title.setStyleSheet("font-weight: bold; font-size: 15px; color: #37474F;")

        f_info = QFormLayout()
        f_info.setSpacing(8)
        f_info.addRow("🖥️ <b>Сервер СУБД:</b>", QLabel(f"PostgreSQL ({settings.DB_HOST}:{settings.DB_PORT})"))
        f_info.addRow("🗄️ <b>База данных / Схема:</b>", QLabel(f"{settings.DB_NAME} / {settings.DB_SCHEMA}"))
        f_info.addRow("🔒 <b>Шифрование ПДн:</b>", QLabel("pgcrypto AES-256 (активно по 152-ФЗ)"))
        f_info.addRow("🕒 <b>Часовой пояс СУБД:</b>", QLabel("Asia/Irkutsk (UTC+8, г. Братск)"))
        f_info.addRow("📦 <b>Версия комплекса:</b>", QLabel("School Psychology Testing App v5.2 Stable"))

        lay_i.addWidget(lbl_i_title)
        lay_i.addLayout(f_info)
        layout.addWidget(card_info)

        layout.addStretch()
        scroll.setWidget(container)
        page_layout.addWidget(scroll)

        # Первичное обновление статуса бэкапа
        self.refresh_backup_status()

        return page


    # ============================================================
    # ⚙️ СЛОТЫ УПРАВЛЕНИЯ ВКЛАДКОЙ «ОПЦИИ»
    # ============================================================

    def refresh_backup_status(self):
        """Обновление надписи о последнем бэкапе в интерфейсе."""
        if not hasattr(self, 'lbl_backup_status') or not self.lbl_backup_status:
            return
        info = self.db_service.get_last_backup_info()
        if info:
            d_str = info['date'].strftime('%d.%m.%Y %H:%M') if info.get('date') else "---"
            sz_mb = round((info.get('size', 0) / (1024 * 1024)), 2)
            self.lbl_backup_status.setText(
                f"✅ Последняя резервная копия создана: <b>{d_str}</b> (размер: {sz_mb} МБ)."
            )
        else:
            self.lbl_backup_status.setText("ℹ️ Резервные копии еще не создавались.")

    @Slot()
    def on_create_backup_clicked(self):
        """Слот ручного запуска резервного копирования базы данных."""
        from datetime import datetime
        import os

        # Предлагаем имя файла по умолчанию с датой и временем
        cur_date = datetime.now().strftime('%Y-%m-%d_%H-%M')
        def_name = f"school_psychology_backup_{cur_date}.sql"

        # Создаем папку backups в корне проекта, если её нет
        default_dir = os.path.join(os.getcwd(), "backups")
        os.makedirs(default_dir, exist_ok=True)
        default_path = os.path.join(default_dir, def_name)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить резервную копию базы данных",
            default_path,
            "SQL Dump (*.sql);;All Files (*)"
        )
        if not file_path:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            success, err_msg = self.db_service.create_database_backup(
                backup_filepath=file_path,
                user_id=self.user_data.get('id')
            )
            QApplication.restoreOverrideCursor()

            if success:
                self.refresh_backup_status()
                QMessageBox.information(
                    self,
                    "Успех",
                    f"Резервная копия базы данных успешно сформирована!\n\n"
                    f"📍 Путь к файлу:\n{file_path}\n\n"
                    f"Запись зафиксирована в системном журнале бэкапов."
                )
            else:
                QMessageBox.critical(
                    self,
                    "Ошибка бэкапа",
                    f"Не удалось завершить создание резервной копии:\n{err_msg}"
                )
        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.error(f"Backup exception: {e}")
            QMessageBox.critical(self, "Критический сбой", f"Сбой процесса резервирования:\n{e}")

    @Slot()
    def on_open_backup_folder_clicked(self):
        """Слот открытия проводника в каталоге бэкапов."""
        import os
        import subprocess

        b_dir = os.path.join(os.getcwd(), "backups")
        os.makedirs(b_dir, exist_ok=True)
        try:
            if os.name == 'nt':
                os.startfile(b_dir)
            else:
                subprocess.Popen(['xdg-open', b_dir])
        except Exception as e:
            QMessageBox.warning(self, "Открытие папки", f"Не удалось открыть каталог:\n{e}")

    @Slot()
    def on_export_audit_clicked(self):
        """Слот выгрузки журналов аудита 152-ФЗ в Excel."""
        from datetime import datetime
        cur_date = datetime.now().strftime('%Y-%m-%d')
        def_name = f"Журнал_аудита_152ФЗ_{cur_date}.xlsx"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Выгрузить журнал аудита безопасности",
            def_name,
            "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.db_service.export_audit_logs_to_excel(file_path)
            QApplication.restoreOverrideCursor()
            QMessageBox.information(
                self,
                "Аудит выгружен",
                f"Журнал аудита действий и выгрузок протоколов успешно сохранен:\n\n"
                f"📍 {file_path}\n\n"
                f"Файл готов для предоставления при проверках соответствия 152-ФЗ."
            )
        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.error(f"Audit export error: {e}")
            QMessageBox.critical(self, "Ошибка выгрузки", f"Не удалось сформировать отчет аудита:\n{e}")

    @Slot()
    def on_open_app_log_clicked(self):
        """Слот открытия файла app.log в Блокноте."""
        import os
        log_path = os.path.join(os.getcwd(), "logs", "app.log")
        if not os.path.exists(log_path):
            QMessageBox.warning(self, "Логи", "Файл logs/app.log пока не содержит записей.")
            return
        try:
            if os.name == 'nt':
                os.startfile(log_path)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', log_path])
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл логов:\n{e}")

    @Slot()
    def on_change_password_clicked(self):
        """Слот вызова модального диалога смены пароля текущего пользователя."""
        dialog = ChangePasswordDialog(
            auth_service=self.auth_service,
            db_service=self.db_service,
            user_data=self.user_data,
            parent=self
        )
        dialog.exec()


    
    @Slot()
    def on_export_report_clicked(self):
        """🚀 Профессиональное формирование Word-отчета и сохранение в БД (Senior V10.5)"""
        # Проверка выбора
        row = self.results_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Выбор", "Пожалуйста, выделите строку с результатом для экспорта!")
            return

        # Извлекаем UUID сессии (скрытая первая колонка)
        session_uuid = self.results_table.item(row, 0).text()
        
        try:
            # 1. Загрузка полных данных
            report_data = self.db_service.get_detailed_report_data(session_uuid)
            
            if not report_data or report_data.get('student') is None:
                QMessageBox.critical(self, "Ошибка БД", "Не удалось найти записи об этом тестировании.")
                return

            # 2. Безопасная дешифровка фамилии
            def safe_name_decode(field):
                if field is None:
                    return "Ученик"
                try:
                    return field.tobytes().decode('utf-8') if hasattr(field, 'tobytes') else str(field)
                except Exception: 
                    return "Ученик"

            student_name = safe_name_decode(report_data['student'][1])
            
            # 3. Название файла
            date_now = datetime.now().strftime('%Y-%m-%d_%H-%M')
            default_filename = f"Протокол_{student_name}_{date_now}.docx"

            # 4. ДИАЛОГ ВЫБОРА МЕСТА (Где психолог укажет на компьютере)
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Выберите место для сохранения отчета", default_filename, "Word Documents (*.docx)"
            )
            
            if file_path:
                from src.services.report_service import ReportService
                
                # А. СОХРАНЯЕМ ФИЗИЧЕСКИ НА КОМПЬЮТЕР
                ReportService.generate_docx_report(report_data, file_path)
                
                # Б. СЧИТЫВАЕМ ТОЛЬКО ЧТО СОЗДАННЫЙ ФАЙЛ В БАЙТЫ (для БД)
                with open(file_path, 'rb') as f:
                    file_blob = f.read()
                
                # В. СОХРАНЯЕМ В БД (test_reports)
                # Вызываем метод, который мы добавили в Шаге 1
                self.db_service.archive_report_to_db(
                    session_id=session_uuid,
                    file_path=file_path,
                    file_bytes=file_blob, # Данные файла
                    user_id=self.user_data.get('id') # ID того, кто скачал
                )
                
                
                QMessageBox.information(
                    self, 
                    "Успех!", 
                    f"Документ успешно сформирован для: {student_name}.\n\n"
                    f"📍 Путь: {file_path}\n"
                    f"☁️ Статус: Копия сохранена в базу данных."
                )
                logger.info(f"✅ Успешный экспорт и архивация отчета для сессии {session_uuid}")

        except Exception as err:
            logger.error(f"❌ Сбой экспорта/архивации: {err}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Критическая ошибка", f"Сбой процесса формирования отчета:\n{str(err)}")
    
    
    
    # ============================================================
    # 🧠 ЛОГИКА СИНХРОНИЗАЦИИ И СЛОТЫ ОБРАБОТКИ
    # ============================================================

    def manual_refresh_all(self):
        """Метод вызывается по нажатию кнопки синхронизации. Обновляет все списки."""
    
        try:
            self.refresh_classes_table()
            self.refresh_filter_combo()
            self.refresh_students_table()
            self.refresh_users_table()
            self.refresh_tests_table()
            self.refresh_results_table()
            self.update_notif_counter() # ✨ Добавь эту строчку
            QApplication.processEvents()
            logger.info("Manual synchronization triggered by user.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка синхронизации", str(e))

    def refresh_filter_combo(self):
        """Заполняет выпадающий список выбора классов на вкладке Ученики."""
        if not self.student_class_filter:
            return
            
        self.student_class_filter.blockSignals(True)
        # Запоминаем текущий выбор
        saved_id = self.student_class_filter.currentData()
        
        self.student_class_filter.clear()
        self.student_class_filter.addItem("🔎 Показать всех учащихся", None)
        
        try:
            clss_rows = self.db_service.get_all_classes()
            for cid, name, _, _ in clss_rows:
                self.student_class_filter.addItem(f"Группа {name}", cid)
        except Exception:
            pass
            
        # Восстанавливаем выделение
        index = self.student_class_filter.findData(saved_id)
        self.student_class_filter.setCurrentIndex(index if index >= 0 else 0)
        self.student_class_filter.blockSignals(False)

    @Slot(int, int)
    def on_class_double_clicked(self, row, col):
        """Двойной клик на класс: переносит во вкладку Ученики с предустановленным фильтром."""
        try:
            cid = self.classes_table.item(row, 0).text()
            index = self.student_class_filter.findData(cid)
            if index >= 0:
                self.student_class_filter.setCurrentIndex(index)
            # Переключение на вкладку учащихся (индекс 3)
            self.tabs.setCurrentIndex(3)
        except Exception:
            pass

    def refresh_students_table(self):
        """
        🚀 Профессиональный рендер списка учащихся (Senior V11.0).
        Синхронизировано с 12-колонной структурой БД (ФИО + Дата + Пол + Класс).
        """
        if not self.students_table:
            return
            
        # 1. Сброс состояния таблицы
        self.students_table.setRowCount(0)
        
        # Получаем параметры фильтрации
        filter_cid = self.student_class_filter.currentData()
        # Приводим поисковый запрос к нижнему регистру один раз
        search_query = self.student_search_input.text().strip().lower()
        
        try:
            # 2. Запрос расширенных данных из DatabaseService
            # Ожидаемый кортеж d: 
            # [0]:id, [1]:code, [2]:fname_enc, [3]:lname_enc, [4]:mname_enc, [5]:birth_date, [6]:gender, [7]:class_name
            res_students = self.students_service.get_students_by_class(filter_cid)
            
            # Внутренняя функция для безопасной дешифровки BYTEA полей
            def safe_byte_decode(value) -> str:
                if value is None:
                    return ""
                try:
                    # Обработка memoryview (стандарт psycopg2 для bytea)
                    return value.tobytes().decode("utf-8") if hasattr(value, "tobytes") else str(value)
                except Exception:
                    return "---"

            for d in res_students:
                # 3. Дешифровка ФИО для проверки поисковым фильтром
                first_name = safe_byte_decode(d[2])
                last_name = safe_byte_decode(d[3])
                middle_name = safe_byte_decode(d[4])
                
                # Сборка строки для поиска (Фамилия Имя Отчество)
                full_name_string = f"{last_name} {first_name} {middle_name}".lower()

                # 4. ЛОГИКА ФИЛЬТРАЦИИ ПОИСКА
                if not search_query or search_query in full_name_string:
                    row_idx = self.students_table.rowCount()
                    self.students_table.insertRow(row_idx)
                    
                    # --- ЗАПОЛНЕНИЕ ЯЧЕЕК (8 КОЛОНОК) ---
                    
                    # [0, 1] Системные данные
                    self.students_table.setItem(row_idx, 0, QTableWidgetItem(str(d[0])))
                    self.students_table.setItem(row_idx, 1, QTableWidgetItem(str(d[1])))
                    
                    # [2, 3, 4] Расшифрованные ФИО
                    self.students_table.setItem(row_idx, 2, QTableWidgetItem(last_name))
                    self.students_table.setItem(row_idx, 3, QTableWidgetItem(first_name))
                    self.students_table.setItem(row_idx, 4, QTableWidgetItem(middle_name))
                    
                    # [5] Дата рождения (обработка объекта date -> str)
                    b_date_val = d[5].strftime("%d.%m.%Y") if d[5] else "---"
                    self.students_table.setItem(row_idx, 5, QTableWidgetItem(b_date_val))
                    
                    # [6] Пол ученика
                    gender_val = str(d[6]) if d[6] else "---"
                    self.students_table.setItem(row_idx, 6, QTableWidgetItem(gender_val))
                    
                    # [7] Название класса (теперь под индексом 7)
                    class_name_val = d[7] if d[7] else "Не привязан"
                    self.students_table.setItem(row_idx, 7, QTableWidgetItem(class_name_val))

                    # Senior-штрих: Выравнивание текста в системных ячейках по центру
                    self.students_table.item(row_idx, 1).setTextAlignment(Qt.AlignCenter)
                    self.students_table.item(row_idx, 5).setTextAlignment(Qt.AlignCenter)
                    self.students_table.item(row_idx, 6).setTextAlignment(Qt.AlignCenter)

        except Exception as err:
            logger.error(f"🚨 Критическая ошибка отрисовки таблицы учеников: {err}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Ошибка БД", "Не удалось корректно отобразить список учеников.")

    # --- МЕТОДЫ-СЛОТЫ ДЛЯ CRUD УЧЕНИКОВ ---

    def on_add_student_clicked(self):
        dialog = StudentDialog(self.db_service, self)
        if dialog.exec() == QDialog.Accepted:
            d = dialog.get_data()
            try:
                if d["create_account"]:
                    password_hash = self.auth_service.get_password_hash(d["password"])
                    self.students_service.add_student_with_account(
                        d["code"],
                        d["first_name"],
                        d["last_name"],
                        d["middle_name"],
                        d["birth_date"],
                        d["gender"],
                        d["class_id"],
                        d["login"],
                        password_hash,
                        d["consent"],
                    )
                else:
                    self.students_service.add_student(
                        d["code"],
                        d["first_name"],
                        d["last_name"],
                        d["middle_name"],
                        d["birth_date"],
                        d["gender"],
                        d["class_id"],
                        d["consent"],
                    )
                self.manual_refresh_all()
                if d["create_account"]:
                    QMessageBox.information(
                        self,
                        "Ученик создан",
                        "Профиль ученика и учётная запись созданы.\n\n"
                        f"Логин: {d['login']}\n"
                        f"Пароль: {d['password']}\n\n"
                        "Сохраните эти данные и передайте их безопасным способом. "
                        "Пароль хранится в базе только в виде хеша.",
                    )
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось добавить: {e}")


    def on_edit_student_clicked(self):
        row = self.students_table.currentRow()
        if row < 0:
            return
        
        # Собираем данные из таблицы, чтобы диалог их отобразил
        old_data = {
            "id": self.students_table.item(row, 0).text(),
            "code": self.students_table.item(row, 1).text(),
            "last_name": self.students_table.item(row, 2).text(),
            "first_name": self.students_table.item(row, 3).text(),
            "middle_name": self.students_table.item(row, 4).text(),
            "birth_date": self.students_table.item(row, 5).text(), # Дата рожд
            "gender": self.students_table.item(row, 6).text(),     # Пол
            "class_name": self.students_table.item(row, 7).text()
        }
        
        dialog = StudentDialog(self.db_service, self, student_data=old_data)
        if dialog.exec() == QDialog.Accepted:
            d = dialog.get_data()
            try:
                # ✅ Добавлены d['birth_date'] и d['gender']
                self.db_service.update_student(
                    old_data['id'], d['first_name'], d['last_name'], 
                    d['middle_name'], d['birth_date'], d['gender'], d['class_id']
                )
                # ✅ Сохраняем согласие
                self.db_service.set_student_consent(old_data['id'], d['consent'])
                self.manual_refresh_all()
                self.manual_refresh_all()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось обновить: {e}")

    @Slot()
    def on_delete_student_clicked(self):
        """МАССОВОЕ ИЛИ ОДИНОЧНОЕ УДАЛЕНИЕ."""
        selection = self.students_table.selectionModel().selectedRows()
        if not selection:
            QMessageBox.warning(self, "Выбор не сделан", "Выберите строки (через зажатый Ctrl) для удаления.")
            return

        cnt = len(selection)
        confirm_text = f"Удалить выделенные записи учащихся (<b>{cnt} чел.</b>)? Это действие удалит все результаты их тестов."
        
        if QMessageBox.question(self, "🗑️ Массовое удаление", confirm_text) == QMessageBox.Yes:
            try:
                for idx in selection:
                    sid = self.students_table.item(idx.row(), 0).text()
                    self.db_service.delete_student(sid) # Метод вызывается по ID
                
                self.manual_refresh_all()
                QMessageBox.information(self, "Готово", f"Очистка завершена. Записей удалено: {cnt}")
            except Exception as e:
                logger.error(f"Deletion failed: {e}")
                QMessageBox.critical(self, "Крит. ошибка БД", f"Удаление прервано: {str(e)}")




    @Slot()
    def on_manage_access_clicked(self):
        """🔑 Массовая генерация доступов и экспорт списка в Excel."""
        selection = self.students_table.selectionModel().selectedRows()
        if not selection:
            QMessageBox.warning(self, "Выбор", "Сначала выделите учеников в таблице!")
            return

        confirm = QMessageBox.question(
            self, "Доступ", 
            f"Сгенерировать новые пароли для {len(selection)} учеников и создать Excel файл?"
        )
        if confirm != QMessageBox.Yes:
            return

        from datetime import datetime
        from pathlib import Path
        import tempfile

        first_row = selection[0].row()
        class_name = self.students_table.item(first_row, 7).text()
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        default_name = f"Logins_{class_name}_{date_str}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить список доступов", default_name, "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        output_path = Path(file_path)
        try:
            if output_path.exists():
                with output_path.open("ab"):
                    pass
            else:
                with tempfile.TemporaryFile(dir=output_path.parent):
                    pass
        except OSError as error:
            QMessageBox.critical(
                self,
                "Нет доступа к папке",
                f"Не удалось записать файл по выбранному пути:\n{error}\n\n"
                "Учётные записи и пароли не изменялись. Выберите доступную папку, "
                "например Документы или Рабочий стол.",
            )
            return

        # Список для сбора данных в Excel
        export_data = []

        for index in selection:
            try:
                row = index.row()
                student_uuid = self.students_table.item(row, 0).text()
                login = self.students_table.item(row, 1).text()
                last_name = self.students_table.item(row, 2).text()
                first_name = self.students_table.item(row, 3).text()
                class_name = self.students_table.item(row, 7).text()

                # 1. Генерируем временный пароль
                raw_password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                
                # 2. Хешируем и записываем в БД (активируем аккаунт)
                pwd_hash = self.auth_service.get_password_hash(raw_password)
                self.db_service.create_student_account(student_uuid, login, pwd_hash)
                
                # 3. Добавляем в список для экспорта
                export_data.append({
                    "Класс": class_name,
                    "Фамилия": last_name,
                    "Имя": first_name,
                    "Логин": login,
                    "Пароль": raw_password
                })

            except Exception as e:
                logger.error(f"Failed access generation for row {index.row()}: {e}")

        if not export_data:
            return

        # --- БЛОК ЭКСПОРТА В EXCEL ---
        try:
            import pandas as pd

            df = pd.DataFrame(export_data)
            while True:
                try:
                    df.to_excel(file_path, index=False)
                    break
                except OSError as error:
                    logger.error(f"Не удалось сохранить список доступов в {file_path}: {error}")
                    retry_path, _ = QFileDialog.getSaveFileName(
                        self,
                        "Выберите другую папку для списка доступов",
                        str(Path.home() / "Documents" / default_name),
                        "Excel Files (*.xlsx)",
                    )
                    if not retry_path:
                        QMessageBox.critical(
                            self,
                            "Файл не сохранён",
                            "Пароли уже обновлены, но файл не удалось сохранить. "
                            "Доступы не потеряны в базе, однако исходный список паролей "
                            "нужно заново сформировать и сохранить в доступную папку.",
                        )
                        return
                    file_path = retry_path

            QMessageBox.information(
                self,
                "Успех",
                f"Доступы успешно созданы и сохранены в файл:\n{file_path}\n\n"
                "Теперь вы можете распечатать этот список для учеников.",
            )
            logger.info(f"Excel-отчет с паролями экспортирован: {file_path}")

        except ImportError:
            QMessageBox.critical(self, "Ошибка", "Не найдена библиотека Pandas для создания Excel файлов!")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сохранения", f"Не удалось создать Excel файл: {e}")

    @Slot()
    def on_bulk_consent_clicked(self):
        """📋 Массовое или одиночное подтверждение согласий родителей (152-ФЗ)."""
        selection = self.students_table.selectionModel().selectedRows()
        if not selection:
            QMessageBox.warning(self, "Выбор не сделан", "Сначала выделите учеников в таблице!")
            return

        cnt = len(selection)
        confirm_text = f"Оформить юридическое согласие родителей на психодиагностику (152-ФЗ) для <b>{cnt} чел.</b>?"
        
        if QMessageBox.question(self, "📋 Согласие на обработку ПДн", confirm_text) == QMessageBox.Yes:
            try:
                for idx in selection:
                    sid = self.students_table.item(idx.row(), 0).text()
                    self.db_service.set_student_consent(sid, True)
                
                QMessageBox.information(
                    self, 
                    "Успех!", 
                    f"Согласие родителей по 152-ФЗ успешно зафиксировано для {cnt} учащихся.\n"
                    "Теперь они имеют законный доступ к тестированию."
                )
                self.manual_refresh_all()
            except Exception as e:
                logger.error(f"Bulk consent failed: {e}")
                QMessageBox.critical(self, "Ошибка БД", f"Не удалось обновить согласия: {str(e)}")



  
    @Slot()
    def on_revoke_access_clicked(self):
        """🚫 Мгновенно блокирует доступ ученикам в систему."""
        selection = self.students_table.selectionModel().selectedRows()
        if not selection:
            QMessageBox.warning(self, "Выбор", "Выберите учеников для закрытия доступа.")
            return

        if QMessageBox.question(self, "Блокировка", f"Отозвать доступ у выбранных учеников ({len(selection)} чел.)?") == QMessageBox.Yes:
            try:
                for index in selection:
                    row_idx = index.row()
                    student_uuid = self.students_table.item(row_idx, 0).text()
                    # Меняем статус в таблице пользователей на 'is_active = False'
                    self.db_service.revoke_student_access(student_uuid)
                
                QMessageBox.information(self, "Готово", "Доступы аннулированы. Ученики больше не смогут войти в кабинет.")
                logger.info(f"Отозван доступ у {len(selection)} пользователей-студентов.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось изменить статус в БД: {e}")




    @Slot()
    def on_import_excel_clicked(self):
        """📥 УМНЫЙ ИМПОРТ EXCEL (Senior Version V11.1)"""
        
        # 1. Извлекаем ID выбранного класса из выпадающего списка (фильтра)
        target_cid = self.student_class_filter.currentData()
        
        # 2. Если класс не выбран (фильтр на "Все учащиеся"), прерываем импорт с предупреждением
        if not target_cid:
            QMessageBox.warning(self, "⚠️ Класс не указан", "Выберите КЛАСС в списке выше, прежде чем загружать учеников!") 
            return

        # 3. Вызываем системное окно выбора файла (поддерживаем .xlsx, .xls и .csv)
        file_p, _ = QFileDialog.getOpenFileName(self, "Открыть список учеников", "", "Таблицы (*.xlsx *.xls *.csv)")
        
        # 4. Если пользователь просто закрыл окно выбора - выходим из функции
        if not file_p: 
            return
        
        try:
            # 5. Ленивый импорт Pandas внутри метода (для ускорения старта всей программы)
            

            # 6. Определяем расширение файла и считываем данные в объект DataFrame
            if file_p.endswith('.csv'):
                # Авто-определение разделителя (запятая или точка с запятой)
                df = pd.read_csv(file_p, sep=None, engine='python')
            else:
                # Чтение классического Excel файла
                df = pd.read_excel(file_p)
                
            # 7. Нормализуем заголовки колонок: убираем пробелы по краям и переводим в нижний регистр
            df.columns = [str(col).strip().lower() for col in df.columns]
            
            # 8. Создаем карту соответствия "что мы ищем в файле" : "как называем в программе"
            keys_map = {
                "фамилия": "ln", "имя": "fn", "отчество": "mn", "код": "cd",
                "дата": "bd", "пол": "gn" # Поддержка даты рождения и пола в файле
            }
            
            # 9. Интеллектуальный поиск индексов колонок (найдет "Фамилия ученика" как "ln")
            found = {val: next((col for col in df.columns if key in col), None) for key, val in keys_map.items()}

            # 10. Проверка критически важных колонок (без ФИО и Кода импорт невозможен)
            if not all([found['ln'], found['fn'], found['cd']]):
                QMessageBox.critical(self, "Формат файла", "Ошибка заголовков. Убедитесь, что в таблице есть: Фамилия, Имя, Код.")
                return

            # 11. Запуск счетчика успешно добавленных строк
            succ_counter = 0
            
            # 12. Построчный перебор данных таблицы
            for _, row in df.iterrows():
                try:
                    # Извлекаем ФИО и Код, переводя их в чистые строки
                    stud_code  = str(row[found['cd']]).strip()
                    first_name = str(row[found['fn']]).strip()
                    last_name  = str(row[found['ln']]).strip()
                    
                    # Обработка отчества (если колонки нет или она пуста - пишем "")
                    middle_name = ""
                    if found['mn'] and pd.notna(row[found['mn']]):
                        middle_name = str(row[found['mn']]).strip()

                    # 13. Новые метаданные (Дата рождения и Пол)
                    # Если данных в Excel нет - используем дефолты (заглушки)
                    birth_date = "2010-01-01" 
                    if found['bd'] and pd.notna(row[found['bd']]):
                        # Пытаемся конвертировать дату из Excel в формат БД
                        try:
                            val = row[found['bd']]
                            birth_date = pd.to_datetime(val).strftime('%Y-%m-%d')
                        except Exception: # Если дата битая - оставим дефолт
                            pass

                    gender = "Не указан"
                    if found['gn'] and pd.notna(row[found['gn']]):
                        # Нормализация (мужской/м/муж -> Мужской)
                        g_raw = str(row[found['gn']]).lower()
                        gender = "Мужской" if g_raw.startswith('м') else ("Женский" if g_raw.startswith('ж') else "Не указан")

                    # 14. ✅ ВЫЗОВ ОБНОВЛЕННОГО МЕТОДА БД (Все 7 аргументов)
                    self.db_service.add_student(
                        stud_code, 
                        first_name, 
                        last_name, 
                        middle_name, 
                        birth_date,
                        gender,
                        target_cid
                    )
                    succ_counter += 1
                
                # 15. Если строка "кривая" или код-дубликат - пропускаем её и идем дальше
                except Exception as row_err:
                    logger.warning(f"Игнорирована строка при импорте: {row_err}")
                    continue
            
            # 16. Уведомление об успехе
            QMessageBox.information(self, "Импорт завершен", f"Успешно зачислено в класс: {succ_counter} учащихся.")
            
            # 17. Полное обновление всех таблиц и графиков на форме
            self.manual_refresh_all()
            
        except Exception as global_err:
            # 18. В случае критической ошибки файла (например он занят другой программой)
            QMessageBox.critical(self, "Ошибка загрузки", f"Критический сбой чтения файла:\n{str(global_err)}")

    # --- МЕТОДЫ УПРАВЛЕНИЯ КЛАССАМИ (CRUD) ---

    def on_add_class_clicked(self):
        from PySide6.QtWidgets import QInputDialog
        val, ok = QInputDialog.getText(self, "Создать", "Имя нового класса (например, 5Б):")
        if ok and val.strip():
            try:
                g = int("".join(filter(str.isdigit, val)) or 0)
                self.classes_service.add_class(val.strip(), g, "А")
                self.manual_refresh_all()
            except Exception as e:
                QMessageBox.critical(self, "DB Fail", str(e))
            return

    def on_edit_class_clicked(self):
        r = self.classes_table.currentRow()
        if r >= 0:
            cid, oname = self.classes_table.item(r, 0).text(), self.classes_table.item(r, 1).text()
            from PySide6.QtWidgets import QInputDialog
            res, ok = QInputDialog.getText(self, "Правка", f"Изменение названия для {oname}:", text=oname)
            if ok: 
                self.classes_service.update_class(cid, res.strip())
                self.refresh_classes_table()

    def on_delete_class_clicked(self):
        r = self.classes_table.currentRow()
        if r >= 0:
            cid = self.classes_table.item(r, 0).text()
            nm = self.classes_table.item(r, 1).text()
            if QMessageBox.question(self, "?", f"Вы уверены? Удаление класса '{nm}' приведет к расформированию группы учеников.") == QMessageBox.Yes:
                self.classes_service.delete_class(cid)
                self.manual_refresh_all()

    # --- МЕТОДЫ ДЛЯ ТЕСТОВ (ДИАЛОГИ) ---
    def on_add_test_clicked(self):
        diag = TestEditorDialog(self.db_service, self)
        if diag.exec() == QDialog.Accepted:
            self.refresh_tests_table()

    
    @Slot()
    def on_delete_test_clicked(self):
        """Массовое удаление выделенных методик."""
        # 1. Получаем список всех выделенных строк
        selection = self.tests_table.selectionModel().selectedRows()
        
        if not selection:
            QMessageBox.warning(self, "Внимание", "Пожалуйста, выберите хотя бы одну методику для удаления.")
            return

        count = len(selection)
        
        # 2. Подтверждение (разные тексты для одной записи и для нескольких)
        if count == 1:
            row = selection[0].row()
            test_name = self.tests_table.item(row, 2).text() # Название теста
            msg = (
                f"Скрыть методику <b>{test_name}</b> из доступных? "
                "История прохождений сохранится."
            )
        else:
            msg = (
                f"Скрыть выбранные методики (<b>{count} шт.</b>) из доступных? "
                "История прохождений сохранится."
            )

        if QMessageBox.question(self, "Подтверждение удаления", msg) == QMessageBox.Yes:
            try:
                # 3. Собираем список ID перед удалением
                ids_to_remove = []
                for index in selection:
                    tid = self.tests_table.item(index.row(), 0).text()
                    ids_to_remove.append(tid)

                # 4. Цикл удаления в базе данных
                for test_id in ids_to_remove:
                    self.db_service.delete_test(test_id) # Теперь метод точно существует!

                # 5. Обновление интерфейса
                self.refresh_tests_table()
                self.manual_refresh_all() # Чтобы обновить счетчик тестов на главной
                
                QMessageBox.information(self, "Готово", f"Методики удалены: {count} шт.")
                logger.info(f"Администратор удалил тестов: {count}")
                
            except Exception as e:
                logger.error(f"Error bulk deleting tests: {e}")
                QMessageBox.critical(self, "Ошибка БД", f"Не удалось выполнить удаление:\n{str(e)}")



    @Slot()
    def on_edit_test_clicked(self):
        """Открытие редактора для существующей методики"""
        row = self.tests_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Выбор не сделан", "Пожалуйста, выберите тест из таблицы!")
            return
            
        try:
            # Извлекаем базовые данные из таблицы
            test_id = self.tests_table.item(row, 0).text()
            test_code = self.tests_table.item(row, 1).text()
            test_name = self.tests_table.item(row, 2).text()
            
            # Запускаем диалог. Передача test_data переключает диалог в режим РЕДАКТИРОВАНИЯ
            # Он сам пойдет в БД и подтянет вопросы/шкалы по test_id
            dialog = TestEditorDialog(self.db_service, self, test_data=(test_id, test_code, test_name))
            
            if dialog.exec() == QDialog.Accepted:
                self.refresh_tests_table()
                self.manual_refresh_all() # Обновляем статистику на главной, если число вопросов изменилось
        except Exception as e:
            logger.error(f"Error starting test editor: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные теста:\n{str(e)}")

    
    
    @Slot()
    def show_notifications_center(self):
        """Открывает центр уведомлений и актуализирует счетчик на кнопке."""
        # Вызов диалога из Шага 1
        dialog = NotificationDialog(
            db_service=self.db_service, 
            user_id=self.user_data['id'], 
            parent=self
        )
        dialog.exec()
        # После закрытия окна обновляем счетчик непрочитанных
        self.update_notif_counter()

    def update_notif_counter(self):
        """Проверяет базу и пишет количество новых сообщений на кнопке."""
        try:
            # Получаем только непрочитанные
            unread = self.db_service.get_user_notifications(self.user_data['id'], only_unread=True)
            count = len(unread)
            
            if count > 0:
                self.notif_btn.setText(f"🔔 Оповещения ({count})")
                self.notif_btn.setStyleSheet("background-color: #FF5252; color: white; font-weight: bold;") # Красная если есть новое
            else:
                self.notif_btn.setText("🔔 Оповещения")
                self.notif_btn.setStyleSheet("background-color: #3F51B5; color: white; font-weight: bold;")
        except Exception as e:
            logger.error(f"Error updating notification counter: {e}")
            self.notif_btn.setText("🔔 Оповещения")
            self.notif_btn.setStyleSheet("background-color: #3F51B5; color: white; font-weight: bold;")
# ============================================================


# ==========================================================================
# 🏠 ДИАЛОГОВОЕ ОКНО: КАРТОЧКА УЧАЩЕГОСЯ (Senior V11.0)
# ==========================================================================

class StudentDialog(QDialog):
    """
    Класс реализации модального окна для управления данными учащихся.
    Поддерживает режимы: 
    1. Регистрация нового (с автогенерацией UUID-кода).
    2. Редактирование существующего (с подгрузкой данных из БД).
    """
    
    def __init__(self, db_service, parent=None, student_data=None):
        """
        Инициализация диалога.
        :param db_service: Ссылка на DatabaseService для работы с SQL.
        :param student_data: dict, если передан — окно открывается в режиме правки.
        """
        super().__init__(parent)
        
        # Ленивый импорт библиотек внутри метода (ускоряет старт приложения)
        import uuid
        from datetime import datetime

        from PySide6.QtCore import QDate  # Нужно для работы с календарем

        self.db_service = db_service
        self.students_service = StudentsService(db_service)
        self.setWindowTitle("Личная карта учащегося (Служебный доступ)")
        self.setMinimumWidth(550) # Сделали чуть шире для новых полей
        
        # Основной вертикальный макет
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(10)

        # Создаем контейнер формы для аккуратного выравнивания "Название: Поле"
        self.form_container = QWidget()
        self.form = QFormLayout(self.form_container)
        self.form.setLabelAlignment(Qt.AlignRight)
        self.form.setSpacing(12)
        
        # --- 🏗️ ИНИЦИАЛИЗАЦИЯ ПОЛЕЙ ВВОДА ---
        
        # Идентификатор ( student_code )
        self.in_cd = QLineEdit() 
        self.in_cd.setToolTip("Уникальный код генерируется системой автоматически")

        # Личные данные (ФИО)
        self.in_ln = QLineEdit() # Фамилия (last_name)
        self.in_fn = QLineEdit() # Имя (first_name)
        self.in_mn = QLineEdit() # Отчество (middle_name)

        # Демографические данные (Синхронизация с 12-ю колонками БД)
        self.in_bdate = QDateEdit() # birth_date
        self.in_bdate.setCalendarPopup(True) # Включаем всплывающий календарь
        self.in_bdate.setDate(QDate.currentDate().addYears(-10)) # Дефолт - ребенок 10 лет
        self.in_bdate.setDisplayFormat("dd.MM.yyyy")

        self.in_gender = QComboBox() # gender
        self.in_gender.addItems(["Мужской", "Женский", "Не указан"])

        # ✨ Чекбокс согласия по 152-ФЗ
        self.in_consent = QCheckBox("Согласие родителей получено (152-ФЗ)")
        self.in_consent.setStyleSheet("font-weight: bold; color: #2e7d32; margin-top: 5px;")

        self.create_account_check = QCheckBox(
            "Сразу создать ученику учётную запись для входа"
        )
        self.create_account_check.setChecked(True)
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Логин латиницей, цифры и _")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Не менее 8 символов")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Повторите пароль")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)

        self.account_fields = QWidget()
        account_form = QFormLayout(self.account_fields)
        account_form.setContentsMargins(0, 0, 0, 0)
        account_form.addRow("Логин:", self.login_input)
        account_form.addRow("Пароль:", self.password_input)
        account_form.addRow("Повтор пароля:", self.confirm_password_input)
        self.create_account_check.toggled.connect(self.account_fields.setVisible)
        
        # Групповая принадлежность ( class_id )
        self.cb_cl = QComboBox()
        self.cb_cl.setMinimumHeight(35)
        
        # --- 📊 ПОДГРУЗКА РЕАЛЬНЫХ КЛАССОВ ИЗ БД ---
        try:
            cl_list = self.db_service.get_all_classes()
            for cid, name, _, _ in cl_list:
                self.cb_cl.addItem(f"Группа {name}", cid)
        except Exception as e: 
            logger.error(f"UI Error: Не удалось заполнить список классов: {e}")

        # --- 📋 ДОБАВЛЕНИЕ СТРОК В ТАБЛИЦУ ФОРМЫ ---
        self.form.addRow("🆔 Системный код:", self.in_cd)
        self.form.addRow("👤 Фамилия:", self.in_ln)
        self.form.addRow("👤 Имя:", self.in_fn)
        self.form.addRow("👤 Отчество (если есть):", self.in_mn)
        self.form.addRow("📅 Дата рождения:", self.in_bdate)
        self.form.addRow("⚥ Пол ученика:", self.in_gender)
        self.form.addRow("📚 Класс назначения:", self.cb_cl)
        self.form.addRow("📋 Согласие 152-ФЗ:", self.in_consent)
        self.form.addRow("🔐 Доступ в приложение:", self.create_account_check)
        self.form.addRow(self.account_fields)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QScrollArea.NoFrame)
        form_scroll.setWidget(self.form_container)
        main_layout.addWidget(form_scroll)

        # СТАНДАРТНЫЙ БЛОК КНОПОК (Ok / Cancel)
        btns_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns_box.accepted.connect(self.do_validate) # Сначала проверяем данные
        btns_box.rejected.connect(self.reject)
        main_layout.addWidget(btns_box)
        
        # ============================================================
        # 🔑 ЛОГИКА ОПРЕДЕЛЕНИЯ РЕЖИМА (ПРАВКА VS СОЗДАНИЕ)
        # ============================================================
        if student_data:
            self.create_account_check.setChecked(False)
            self.create_account_check.setEnabled(False)
            # РЕЖИМ ПРАВКИ: Подставляем данные из словаря таблицы админа
            self.in_cd.setText(student_data.get('code', ''))
            self.in_cd.setReadOnly(True) # Запрещаем менять код существующему ученику
            self.in_ln.setText(student_data.get('last_name', ''))
            self.in_fn.setText(student_data.get('first_name', ''))
            self.in_mn.setText(student_data.get('middle_name', ''))
            
            # Обработка пола
            current_g = student_data.get('gender', 'Не указан')
            idx_g = self.in_gender.findText(current_g)
            if idx_g >= 0: 
                self.in_gender.setCurrentIndex(idx_g)
            
            # Обработка даты рождения (если в БД не пусто)
            db_date_raw = student_data.get('birth_date')
            if db_date_raw:
                # Конвертируем из строки БД "YYYY-MM-DD" в QDate объект
                self.in_bdate.setDate(QDate.fromString(str(db_date_raw), "yyyy-MM-dd"))
            
            # Установка корректного класса в списке
            target_class = f"Группа {student_data.get('class_name', '')}"
            idx_c = self.cb_cl.findText(target_class)
            if idx_c >= 0: 
                self.cb_cl.setCurrentIndex(idx_c)

            # Подгружаем статус согласия из БД:
            sid = student_data.get('id')
            if sid:
                self.in_consent.setChecked(self.students_service.get_student_consent(sid))
        else:
            # РЕЖИМ СОЗДАНИЯ: Генерируем уникальный маркер ГГГГ-ID
            cur_year = datetime.now().year
            rand_suffix = uuid.uuid4().hex[:6].upper() # 6 случайных символов
            self.in_cd.setText(f"{cur_year}-{rand_suffix}")
            self.login_input.setText(self.in_cd.text().replace("-", "_"))
            
            # Блокируем код от случайных правок пользователем
            self.in_cd.setReadOnly(True)
            self.in_cd.setStyleSheet("background-color: #f2f2f2; color: #555;")

    def do_validate(self):
        """Метод проверки полноты данных перед закрытием диалога."""
        if not self.in_fn.text().strip() or not self.in_ln.text().strip():
            QMessageBox.warning(self, "Внимание", "Не заполнены ФИО ученика. Пожалуйста, введите фамилию и имя!")
            return
        if self.cb_cl.currentData() is None:
            QMessageBox.warning(self, "Класс", "Выберите класс ученика.")
            return
        if self.create_account_check.isChecked():
            login = self.login_input.text().strip()
            password = self.password_input.text()
            confirm_password = self.confirm_password_input.text()
            if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", login):
                QMessageBox.warning(
                    self,
                    "Логин",
                    "Логин должен содержать от 3 до 30 символов: латинские буквы, цифры или _.",
                )
                return
            if len(password) < 8 or len(password.encode("utf-8")) > 72:
                QMessageBox.warning(
                    self,
                    "Пароль",
                    "Пароль должен содержать не менее 8 символов и не более 72 байт в UTF-8.",
                )
                return
            if password != confirm_password:
                QMessageBox.warning(self, "Пароль", "Введённые пароли не совпадают.")
                return
        self.accept()

    def get_data(self) -> dict:
        """
        Упаковывает все введенные данные в словарь для метода add/update_student.
        :return: Словарь параметров, готовый для DatabaseService.
        """
        return {
            "code": self.in_cd.text().strip(),
            "first_name": self.in_fn.text().strip(), 
            "last_name": self.in_ln.text().strip(), 
            "middle_name": self.in_mn.text().strip(), 
            "birth_date": self.in_bdate.date().toString("yyyy-MM-dd"), # Преобразование даты
            "gender": self.in_gender.currentText(), # Пол ученика
            "class_id": self.cb_cl.currentData(), # Берем UUID выбранного класса
            "consent": self.in_consent.isChecked(),
            "create_account": self.create_account_check.isChecked(),
            "login": self.login_input.text().strip(),
            "password": self.password_input.text(),
        }


# ============================================================
# ⚙️ ДИАЛОГ (РЕДАКТОР ПСИХОЛОГИЧЕСКИХ ТЕСТОВ)
# ============================================================
# ==============================================================================
# 📝 МОДУЛЬ: КОНСТРУКТОР ПСИХОЛОГИЧЕСКИХ МЕТОДИК (Senior Edition V12.5)
# ==============================================================================

class TestEditorDialog(QDialog):
    """
    Высокотехнологичный конструктор тестов.
    Позволяет редактировать свойства (название/инструкции), лист утверждений (JSON)
    и настраивать формулы шкал с коэффициентами.
    """

    def __init__(self, db_service, parent=None, test_data=None):
        """
        Инициализация интерфейса инженера тестов с адаптивным размером.
        """
        super().__init__(parent)
        from PySide6.QtWidgets import QTextEdit, QScrollArea, QFrame
        
        self.db_service = db_service
        self.test_id = test_data[0] if test_data else None
        
        self.setWindowTitle("Инженер психологических методик (V7.2 Stable)")
        
        # 1. РАЗРЕШАЕМ менять размер окна и разворачивать на весь экран
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        
        # 2. УМЕНЬШАЕМ стартовый размер (620px вместо 850px) и задаем минимальный
        self.resize(1000, 620)
        self.setMinimumSize(780, 480)
        
        main_container = QVBoxLayout(self)
        main_container.setContentsMargins(15, 12, 15, 12)
        main_container.setSpacing(10)
        
        self.tabs = QTabWidget()
        
        # ------------------------------------------------------------
        # 🏷️ Вкладка 1: СВОЙСТВА (МЕТА-ДАННЫЕ)
        # ------------------------------------------------------------
        self.w1 = QWidget()
        l1 = QFormLayout(self.w1)
        l1.setContentsMargins(20, 15, 20, 15)
        l1.setSpacing(12)

        self.e_code = QLineEdit(test_data[1] if test_data else "")
        self.e_code.setPlaceholderText("Системный код методики (напр. OSR_2026)")
        self.e_code.setMinimumHeight(35)
        
        self.e_name = QLineEdit(test_data[2] if test_data else "")
        self.e_name.setPlaceholderText("Официальное название методики")
        self.e_name.setMinimumHeight(35)
        
        # Текстовые поля с компактной высотой
        self.e_desc = QTextEdit()
        self.e_desc.setPlaceholderText("Цели, задачи и краткая история создания методики...")
        self.e_desc.setMinimumHeight(60)
        self.e_desc.setMaximumHeight(110)
        
        self.e_instr = QTextEdit()
        self.e_instr.setPlaceholderText("Инструкция, которую увидит учащийся ПЕРЕД запуском теста...")
        self.e_instr.setMinimumHeight(70)
        self.e_instr.setMaximumHeight(120)

        l1.addRow("🔑 Уникальный Код:", self.e_code)
        l1.addRow("📝 Название методики:", self.e_name)
        self.e_test_mode = QComboBox()
        self.e_test_mode.addItem("Опросник Да / Нет", "yes_no")
        self.e_test_mode.addItem("Задания с выбором вариантов", "choice")
        l1.addRow("Тип методики:", self.e_test_mode)
        l1.addRow("📄 Описание теста (цели):", self.e_desc)
        l1.addRow("📖 Инструкция ученику:", self.e_instr)
        
        # Оборачиваем свойства в ScrollArea, чтобы текст не выталкивал кнопки
        scroll_w1 = QScrollArea()
        scroll_w1.setWidgetResizable(True)
        scroll_w1.setFrameShape(QFrame.NoFrame)
        scroll_w1.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_w1.setWidget(self.w1)

        # ------------------------------------------------------------
        # ❓ Вкладка 2: ВОПРОСЫ (АНКЕТА)
        # ------------------------------------------------------------
        self.w2 = QWidget()
        l2 = QVBoxLayout(self.w2)
        l2.setContentsMargins(10, 10, 10, 10)
        l2.setSpacing(8)
        
        self.tbl_q = QTableWidget(0, 5)
        self.tbl_q.setHorizontalHeaderLabels(
            ["№", "Текст утверждения / задания", "Ответы и баллы (JSON)", "Настройка рисунков", "Действие"]
        )
        
        h_header_q = self.tbl_q.horizontalHeader()
        h_header_q.setSectionResizeMode(0, QHeaderView.Fixed)
        h_header_q.setSectionResizeMode(1, QHeaderView.Stretch)
        h_header_q.setSectionResizeMode(2, QHeaderView.Interactive)
        h_header_q.setSectionResizeMode(3, QHeaderView.Fixed)
        h_header_q.setSectionResizeMode(4, QHeaderView.Fixed)
        
        self.tbl_q.setColumnWidth(0, 45)
        self.tbl_q.setColumnWidth(2, 230)
        self.tbl_q.setColumnWidth(3, 145)
        self.tbl_q.setColumnWidth(4, 80)
        self.e_test_mode.currentIndexChanged.connect(self.update_question_editor_controls)
        
        l2.addWidget(self.tbl_q)
        
        bq = QPushButton("➕ Добавить новую строку утверждения")
        bq.setMinimumHeight(38)
        bq.setCursor(Qt.PointingHandCursor)
        bq.clicked.connect(self.add_q_row)
        l2.addWidget(bq)

        # ------------------------------------------------------------
        # 📊 Вкладка 3: ПРАВИЛА ОЦЕНКИ (ШКАЛЫ)
        # ------------------------------------------------------------
        self.w3 = QWidget()
        l3 = QVBoxLayout(self.w3)
        l3.setContentsMargins(10, 10, 10, 10)
        l3.setSpacing(8)
        
        self.tbl_s = QTableWidget(0, 7)
        self.tbl_s.setHorizontalHeaderLabels([
            "Фактор/Шкала", "Маппинг №№", "Min", "Max", "Коэф.", "Текст заключения", "Действие"
        ])
        
        h_header_s = self.tbl_s.horizontalHeader()
        h_header_s.setSectionResizeMode(5, QHeaderView.Stretch)
        
        self.tbl_s.setColumnWidth(0, 130)
        self.tbl_s.setColumnWidth(1, 140)
        self.tbl_s.setColumnWidth(2, 50)
        self.tbl_s.setColumnWidth(3, 50)
        self.tbl_s.setColumnWidth(4, 60)
        self.tbl_s.setColumnWidth(6, 80)
        
        l3.addWidget(self.tbl_s)
        
        bs = QPushButton("➕ Сформировать новую шкалу анализа")
        bs.setMinimumHeight(38)
        bs.setCursor(Qt.PointingHandCursor)
        bs.clicked.connect(self.add_s_row)
        l3.addWidget(bs)

        # РЕГИСТРАЦИЯ ВКЛАДОК
        self.tabs.addTab(scroll_w1, "🏷️ Свойства") 
        self.tabs.addTab(self.w2, "❓ Лист вопросов") 
        self.tabs.addTab(self.w3, "📊 Правила оценки")
        main_container.addWidget(self.tabs)
        
        # Кнопки сохранения нижнего уровня
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.on_save)
        self.button_box.rejected.connect(self.reject)
        self.button_box.setStyleSheet("QPushButton { min-width: 110px; min-height: 38px; font-weight: bold; }")
        main_container.addWidget(self.button_box)

        # Если мы в режиме ПРАВКИ — восстанавливаем дерево теста из БД
        if self.test_id: 
            self.load_structure()

    # ==========================================================================
    # 🗑️ ТЕХНИЧЕСКАЯ ЛОГИКА ТАБЛИЦ (УДАЛЕНИЕ И НУМЕРАЦИЯ)
    # ==========================================================================

    def create_del_btn(self, table: QTableWidget) -> QPushButton:
        """Создание кнопки удаления с динамическим определением позиции."""
        btn = QPushButton("🗑️")
        btn.setFixedWidth(40)
        btn.setObjectName("cancelButton")
        btn.setCursor(Qt.PointingHandCursor)
        # Связываем нажатие с общим методом удаления строки
        btn.clicked.connect(lambda: self.remove_row_logic(table, btn))
        return btn

    def remove_row_logic(self, table, button):
        """Механика удаления строки и синхронного пересчета индексов."""
        row_idx = next(
            (
                row
                for row in range(table.rowCount())
                if any(
                    table.cellWidget(row, column) is button
                    for column in range(table.columnCount())
                )
            ),
            -1,
        )
        if row_idx >= 0:
            table.removeRow(row_idx)
            # Перенумерация только если удален ВОПРОС (чтобы не ломать маппинг)
            if table == self.tbl_q:
                self.update_question_numbers()

    def update_question_numbers(self):
        """Принудительная нормализация порядковых номеров во 2-й вкладке."""
        self.tbl_q.blockSignals(True)
        try:
            for row in range(self.tbl_q.rowCount()):
                item = QTableWidgetItem(str(row + 1))
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(Qt.ItemIsEnabled) # Защита от ручной правки №
                self.tbl_q.setItem(row, 0, item)
        finally:
            self.tbl_q.blockSignals(False)

    # ==========================================================================
    # 🏗️ СЕРВИСНЫЕ МЕТОДЫ ДОБАВЛЕНИЯ СТРОК (ADD ROWS)
    # ==========================================================================

    def add_q_row(self, data=None):
        """Безопасное создание строки вопроса."""
        row = self.tbl_q.rowCount()
        self.tbl_q.insertRow(row)
        
        # Индекс 0: Номер (генерируется автоматом)
        num_item = QTableWidgetItem(str(row + 1))
        num_item.setTextAlignment(Qt.AlignCenter)
        num_item.setFlags(Qt.ItemIsEnabled)
        self.tbl_q.setItem(row, 0, num_item)
        
        # Извлечение текста (Защита от 'tuple object has no attribute get')
        if isinstance(data, dict):
            payload = dict(data)
            q_text = str(payload.get("text", ""))
            raw_opts = payload.get(
                "options",
                {"Да": 1, "Нет": 0}
                if self.e_test_mode.currentData() == "yes_no"
                else {
                    "selection_mode": "single",
                    "options": [
                        {"id": uuid.uuid4().hex, "text": "", "value": 0},
                        {"id": uuid.uuid4().hex, "text": "", "value": 0},
                    ],
                },
            )
            question_type = str(payload.get("question_type", "single_choice"))
            media_content = payload.get("media_content", {})
            media_assets = payload.get("media_assets", [])
        elif isinstance(data, (tuple, list)):
            q_text = str(data[0] if len(data) > 0 else "")
            raw_opts = data[1] if len(data) > 1 else {"Да": 1, "Нет": 0}
            question_type = str(data[3]) if len(data) > 3 else "single_choice"
            media_content = data[4] if len(data) > 4 else {}
            media_assets = data[5] if len(data) > 5 else []
        else:
            q_text = ""
            if self.e_test_mode.currentData() == "choice":
                raw_opts = {
                    "selection_mode": "single",
                    "options": [
                        {"id": uuid.uuid4().hex, "text": "", "value": 0},
                        {"id": uuid.uuid4().hex, "text": "", "value": 0},
                    ],
                }
            else:
                raw_opts = {"Да": 1, "Нет": 0}
            question_type = "single_choice"
            media_content = {}
            media_assets = []
            payload = {}

        options_text = (
            json.dumps(raw_opts, ensure_ascii=False)
            if isinstance(raw_opts, (dict, list))
            else str(raw_opts)
        )
        payload.update(
            {
                "text": q_text,
                "options": raw_opts,
                "question_type": question_type,
                "media_content": media_content or {},
                "media_assets": media_assets or [],
            }
        )
        question_item = QTableWidgetItem(q_text)
        question_item.setData(Qt.UserRole, payload)
        self.tbl_q.setItem(row, 1, question_item)
        self.tbl_q.setItem(row, 2, QTableWidgetItem(options_text))

        configure_button = QPushButton("Настроить…")
        configure_button.clicked.connect(
            lambda checked=False, button=configure_button:
            self.configure_question_row(button)
        )
        self.tbl_q.setCellWidget(row, 3, configure_button)
        self.tbl_q.setCellWidget(row, 4, self.create_del_btn(self.tbl_q))
        self.update_question_editor_controls()

    def update_question_editor_controls(self, _index=None) -> None:
        """Enable rich option/image editing only for the choice-based methodology."""
        is_choice_method = self.e_test_mode.currentData() == "choice"
        for row in range(self.tbl_q.rowCount()):
            button = self.tbl_q.cellWidget(row, 3)
            if button:
                button.setEnabled(is_choice_method)
                button.setToolTip(
                    ""
                    if is_choice_method
                    else "Для этого типа методики используйте таблицу баллов JSON."
                )

    def configure_question_row(self, button: QPushButton) -> None:
        row = next(
            (
                index
                for index in range(self.tbl_q.rowCount())
                if self.tbl_q.cellWidget(index, 3) is button
            ),
            -1,
        )
        if row < 0:
            return

        text_item = self.tbl_q.item(row, 1)
        options_item = self.tbl_q.item(row, 2)
        payload = dict(text_item.data(Qt.UserRole) or {})
        payload["text"] = text_item.text() if text_item else ""
        try:
            payload["options"] = json.loads(options_item.text()) if options_item else {}
        except json.JSONDecodeError as error:
            QMessageBox.warning(
                self,
                "Некорректные варианты",
                f"Исправьте JSON вариантов перед настройкой рисунков:\n{error}",
            )
            return

        dialog = QuestionEditorDialog(payload, self)
        if dialog.exec() != QDialog.Accepted:
            return

        updated_payload = dialog.get_question_data()
        text_item.setText(updated_payload["text"])
        text_item.setData(Qt.UserRole, updated_payload)
        options_item.setText(
            json.dumps(updated_payload["options"], ensure_ascii=False)
        )

    def add_s_row(self, data=None):
        """
        🚀 Senior Logic: Создание строки правила оценки (шкалы).
        Поддерживает 7 колонок: [0]Фактор, [1]Маппинг, [2]Min, [3]Max, [4]Коэф., [5]Заключение, [6]Действие.
        """
        row_pos = self.tbl_s.rowCount()
        self.tbl_s.insertRow(row_pos)
        
        # Разбор входного пакета данных (Безопасное извлечение)
        if isinstance(data, (tuple, list)):
            # Синхронизация с методом DatabaseService.get_test_full_structure (Индексы 0-5)
            s_nm = data[0] if len(data) > 0 else "Новая шкала"
            s_mp = data[1] if len(data) > 1 else ""
            s_mi = data[2] if len(data) > 2 else 0
            s_mx = data[3] if len(data) > 3 else 10
            s_in = data[4] if len(data) > 4 else ""
            s_cf = data[5] if len(data) > 5 else 1.0
        elif isinstance(data, dict):
            # Если данные переданы как словарь (через UI или Excel)
            s_nm = data.get('name', 'Фактор')
            s_mp = data.get('mapping', '')
            s_mi = data.get('min', 0)
            s_mx = data.get('max', 10)
            s_in = data.get('interpretation', '')
            s_cf = data.get('coef', 1.0)
        else:
            # Для абсолютно новой пустой строки (нажата кнопка '+')
            s_nm, s_mp, s_mi, s_mx, s_in, s_cf = "Фактор", "", 0, 10, "Результат анализа...", 1.0

        # --- СОЗДАНИЕ И ОФОРМЛЕНИЕ ЯЧЕЕК ---
        # Мы используем str(x or '') для исключения текста "None" в интерфейсе
        
        items = [
            str(s_nm or ""),      # 0
            str(s_mp or ""),      # 1
            str(s_mi if s_mi is not None else 0),   # 2
            str(s_mx if s_mx is not None else 10),  # 3
            str(s_cf if s_cf is not None else 1.0), # 4
            str(s_in or "")       # 5
        ]

        for col_idx, text in enumerate(items):
            cell_item = QTableWidgetItem(text)
            
            # Для числовых колонок (1, 2, 3, 4) делаем выравнивание по центру
            if col_idx in [1, 2, 3, 4]:
                cell_item.setTextAlignment(Qt.AlignCenter)
            
            # ✨ ДОПОЛНИТЕЛЬНО: Всплывающая подсказка для длинных текстов заключения
            if col_idx == 5:
                cell_item.setToolTip(f"<b>Заключение по шкале:</b><br>{text}")
                
            self.tbl_s.setItem(row_pos, col_idx, cell_item)

        # 6. Вставка виджета кнопки удаления (🗑️)
        # Мы не создаем элемент, а ставим кнопку как Widget
        self.tbl_s.setCellWidget(row_pos, 6, self.create_del_btn(self.tbl_s))
        
        logger.debug(f"Row {row_pos} initialized in Rules tab.")

    # ==========================================================================
    # 💾 БИЗНЕС-ЛОГИКА: СИНХРОНИЗАЦИЯ С PostgreSQL
    # ==========================================================================

    def load_structure(self) -> None:
        """Синхронизация с БД и загрузка данных в формы."""
        if not self.test_id: 
            return
        self.setUpdatesEnabled(False) # Отключаем мерцание при загрузке
        try:
            # Получаем 3 объекта из DatabaseService
            qs_db, sc_db, meta_db = self.db_service.get_test_full_structure(self.test_id)
            
            # Свойства (Сверху)
            self.e_code.setText(str(meta_db.get('code') or ''))
            self.e_name.setText(str(meta_db.get('name') or ''))
            self.e_desc.setPlainText(str(meta_db.get('desc') or ''))
            self.e_instr.setPlainText(str(meta_db.get('instructions') or ''))
            mode_index = self.e_test_mode.findData(
                str(meta_db.get("test_mode", "yes_no"))
            )
            self.e_test_mode.setCurrentIndex(max(mode_index, 0))

            # Вопросы
            self.tbl_q.setRowCount(0)
            if qs_db:
                for q_unit in qs_db: 
                    self.add_q_row(data=q_unit)

            # Шкалы (Правила)
            self.tbl_s.setRowCount(0)
            if sc_db:
                for s_unit in sc_db: 
                    self.add_s_row(data=s_unit)

            # ✅ ПРАВИЛЬНОЕ ИМЯ: У тебя в __init__ создана self.tabs
            self.tabs.setCurrentIndex(0)

        except Exception as error:
            logger.error(f"Structure Render Fail: {error}")
            QMessageBox.critical(self, "Ошибка БД", f"Не удалось прочитать тест: {error}")
            self.reject()
        finally:
            self.setUpdatesEnabled(True)
    
    @Slot()
    def on_save(self):
        """
        🚀 Senior Logic V12.5: Атомарное сохранение всей структуры методики.
        Собирает свойства, вопросы с JSON-весами и правила оценки с коэффициентами.
        """
        created_test_id = None
        try:
            # --- 1. ЧТЕНИЕ И ВАЛИДАЦИЯ ОСНОВНЫХ СВОЙСТВ ---
            t_code = self.e_code.text().strip()
            t_name = self.e_name.text().strip()
            # Важно: используем toPlainText() для QTextEdit
            t_desc = self.e_desc.toPlainText().strip()
            t_instr = self.e_instr.toPlainText().strip()

            if not t_code or not t_name:
                QMessageBox.warning(self, "Внимание", "Не заполнены обязательные поля: 'Код' или 'Название' методики.")
                return

            test_mode = str(self.e_test_mode.currentData() or "yes_no")

            # --- 2. СБОР ЛИСТА ВОПРОСОВ (Таблица tbl_q) ---
            q_pack = []
            for r in range(self.tbl_q.rowCount()):
                it_txt = self.tbl_q.item(r, 1)
                it_opt = self.tbl_q.item(r, 2)
                
                # Игнорируем пустые строки (проверка на существование объекта и текста)
                if not it_txt or not it_txt.text().strip():
                    continue

                try:
                    raw_json = it_opt.text().strip() if it_opt else ""
                    options = json.loads(raw_json)
                except json.JSONDecodeError as error:
                    QMessageBox.warning(
                        self,
                        "Некорректные варианты ответа",
                        f"В вопросе №{r + 1} указан некорректный JSON:\n{error}",
                    )
                    return

                payload = dict(it_txt.data(Qt.UserRole) or {})
                if test_mode == "choice":
                    choices = options.get("options") if isinstance(options, dict) else None
                    if not isinstance(choices, list) or len(choices) < 2:
                        QMessageBox.warning(
                            self,
                            "Не настроено задание",
                            f"Настройте не менее двух вариантов для задания №{r + 1}.",
                        )
                        return
                    if options.get("selection_mode") not in ("single", "multiple"):
                        QMessageBox.warning(
                            self,
                            "Не настроен выбор",
                            f"Выберите одиночный или множественный выбор для задания №{r + 1}.",
                        )
                        return
                    option_ids = set()
                    for option_index, option in enumerate(choices, start=1):
                        if not isinstance(option, dict) or not option.get("id"):
                            QMessageBox.warning(
                                self,
                                "Некорректный вариант",
                                f"Вариант №{option_index} задания №{r + 1} не имеет идентификатора.",
                            )
                            return
                        option_id = str(option["id"])
                        if option_id in option_ids:
                            QMessageBox.warning(
                                self,
                                "Повтор варианта",
                                f"Идентификатор варианта №{option_index} задания №{r + 1} повторяется.",
                            )
                            return
                        option_ids.add(option_id)
                        if not str(option.get("text", "")).strip() and not option.get("media_key"):
                            QMessageBox.warning(
                                self,
                                "Пустой вариант",
                                f"Укажите текст или рисунок для варианта №{option_index} задания №{r + 1}.",
                            )
                            return
                        try:
                            score = float(str(option.get("value", 0)).replace(",", "."))
                        except (TypeError, ValueError):
                            QMessageBox.warning(
                                self,
                                "Некорректный балл",
                                f"Укажите числовой балл для варианта №{option_index} задания №{r + 1}.",
                            )
                            return
                        if not math.isfinite(score) or score < 0:
                            QMessageBox.warning(
                                self,
                                "Некорректный балл",
                                "Укажите конечное неотрицательное значение баллов.",
                            )
                            return

                    q_type = str(payload.get("question_type", "single_choice"))
                    media_content = payload.get("media_content", {})
                    media_assets = payload.get("media_assets", [])
                else:
                    if not isinstance(options, dict):
                        QMessageBox.warning(
                            self,
                            "Некорректные баллы",
                            f"Для методики Да / Нет в вопросе №{r + 1} ожидался JSON-объект.",
                        )
                        return
                    q_type = "single_choice"
                    media_content = {}
                    media_assets = []

                q_pack.append(
                    {
                        "order": r + 1,
                        "text": it_txt.text().strip(),
                        "options": options,
                        "question_type": q_type,
                        "media_content": media_content,
                        "media_assets": media_assets,
                    }
                )

            # Проверка наличия контента перед транзакцией
            if not q_pack:
                QMessageBox.warning(self, "Пустая методика", "Невозможно сохранить тест без вопросов.")
                return

            # --- 3. СБОР ПРАВИЛ ОЦЕНКИ (Таблица tbl_s: 7 колонок) ---
            s_pack = []

            # Внутренний хелпер для безопасного считывания чисел ( Senior Style )
            def clean_num_safe(item, default=1.0):
                if not item or not item.text().strip():
                    return default
                try:
                    # Меняем русские запятые на точки и чистим пробелы
                    return float(item.text().replace(',', '.').strip())
                except (ValueError, TypeError):
                    return default

            for r in range(self.tbl_s.rowCount()):
                # Колонки: 0:Фактор, 1:Маппинг, 2:Min, 3:Max, 4:Коэф, 5:Заключение
                it_nm = self.tbl_s.item(r, 0)
                it_mp = self.tbl_s.item(r, 1)
                it_mi = self.tbl_s.item(r, 2)
                it_mx = self.tbl_s.item(r, 3)
                it_cf = self.tbl_s.item(r, 4)
                it_it = self.tbl_s.item(r, 5)

                if not it_nm or not it_nm.text().strip():
                    continue

                # ✨ Очистка маппинга от всех пробелов (чтобы SQL видел "1,2,3" вместо "1, 2 , 3")
                mapping_clean = it_mp.text().strip().replace(' ', '') if it_mp else ""

                s_pack.append({
                    'name': it_nm.text().strip(),
                    'mapping': mapping_clean,
                    'min': int(clean_num_safe(it_mi, 0)),
                    'max': clean_num_safe(it_mx, 10.0),
                    'coef': clean_num_safe(it_cf, 1.0),
                    'interpretation': it_it.text().strip() if it_it else ""
                })

            # --- 4. ВЗАИМОДЕЙСТВИЕ С БАЗОЙ ДАННЫХ (Транзакционный блок) ---
            test_config = {"test_mode": test_mode}
            if not self.test_id:
                self.test_id = self.db_service.add_test(
                    t_code, t_name, t_desc, t_instr, test_config
                )
                created_test_id = self.test_id
                logger.info(f"Создан новый тест. Получен UUID: {self.test_id}")
                self.db_service.save_test_structure(self.test_id, q_pack, s_pack)
            else:
                self.db_service.ensure_test_structure_editable(self.test_id)
                self.db_service.save_test_structure(
                    self.test_id,
                    q_pack,
                    s_pack,
                    metadata={
                        "code": t_code,
                        "name": t_name,
                        "description": t_desc,
                        "instructions": t_instr,
                        "config": test_config,
                    },
                )

            # --- 5. ОБНОВЛЕНИЕ ГРАФИЧЕСКОГО ИНТЕРФЕЙСА (Refresh UI) ---
            # Поиск родительского Dashboard для обновления списка тестов на главном экране
            current_parent = self.parent()
            while current_parent:
                if hasattr(current_parent, 'refresh_tests_table'):
                    current_parent.refresh_tests_table()
                    break
                current_parent = current_parent.parent()

            QMessageBox.information(
                self, 
                "✅ Сохранено успешно", 
                f"Методика '{t_name}' полностью синхронизирована с базой данных школы."
            )
            self.accept()

        except Exception as global_error:
            # Обработка всех непредвиденных сбоев (БД, типы, JSON)
            logger.error(f"FATAL ERROR during test save: {global_error}")
            if created_test_id:
                try:
                    self.db_service.delete_test(created_test_id)
                except Exception as cleanup_error:
                    logger.error(
                        "Не удалось архивировать незавершенную методику %s: %s",
                        created_test_id,
                        cleanup_error,
                    )
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self, 
                "Критическая ошибка сохранения", 
                f"Система не смогла записать данные.\n\nПричина: {str(global_error)}"
            )
            



class NotificationDialog(QDialog):
    """Модальное окно центра уведомлений (Senior Style)"""
    def __init__(self, db_service, user_id, parent=None):
        super().__init__(parent)
        self.db_service = db_service
        self.user_id = user_id
        
        self.setWindowTitle("🔔 Центр уведомлений системы")
        self.setFixedSize(650, 450)
        self.setStyleSheet(load_stylesheet())
        
        layout = QVBoxLayout(self)
        
        # Таблица уведомлений
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Дата", "Категория", "Тема", "Статус"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.table)
        
        # Кнопки управления
        btn_layout = QHBoxLayout()
        self.btn_mark_read = QPushButton("📖 Прочитать")
        self.btn_delete = QPushButton("🗑️ Очистить")
        self.btn_delete.setObjectName("cancelButton") # Красная кнопкаhelder
        
        self.btn_mark_read.clicked.connect(self.on_mark_read)
        self.btn_delete.clicked.connect(self.on_delete)
        
        btn_layout.addWidget(self.btn_mark_read)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.refresh_data()

    def refresh_data(self):
        """Обновление списка уведомлений с улучшенной визуализацией (Senior V11.5)"""
        # 1. Защита интерфейса: отключаем отрисовку на время массовой вставки
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(0)
        
        try:
            # Получаем данные: id[0], title[1], message[2], type[3], is_read[4], date[5]
            notifications = self.db_service.get_user_notifications(self.user_id)
            
            for i, row in enumerate(notifications):
                n_id, n_title, n_message, n_type, is_read, n_date = row
                
                self.table.insertRow(i)
                
                # --- ПОДГОТОВКА ЭЛЕМЕНТОВ ---
                
                # Колонка 0: Дата
                date_str = str(n_date)[:16] if n_date else "---"
                item_date = QTableWidgetItem(date_str)
                item_date.setTextAlignment(Qt.AlignCenter)
                
                # Колонка 1: Категория (тип)
                type_text = str(n_type).upper()
                item_type = QTableWidgetItem(type_text)
                item_type.setTextAlignment(Qt.AlignCenter)
                
                # Цветовая схема типов
                if n_type in ['warning', 'danger', 'критично']:
                    item_type.setForeground(Qt.red)
                elif n_type in ['info', 'system']:
                    item_type.setForeground(Qt.blue)
                
                # Колонка 2: Заголовок
                item_title = QTableWidgetItem(str(n_title))
                item_title.setToolTip(str(n_message)) # Показ текста сообщения при наведении
                item_title.setData(Qt.UserRole, str(n_id)) # UUID для методов mark_read/delete
                
                # Колонка 3: Статус
                status_text = "✓ Просмотрено" if is_read else "НОВОЕ ✨"
                item_status = QTableWidgetItem(status_text)
                item_status.setTextAlignment(Qt.AlignCenter)
                
                # --- ВИЗУАЛЬНЫЕ АКЦЕНТЫ ДЛЯ НЕПРОЧИТАННЫХ ---
                if not is_read:
                    bold_font = item_status.font()
                    bold_font.setBold(True)
                    item_status.setFont(bold_font)
                    item_title.setFont(bold_font)
                    item_status.setForeground(Qt.darkBlue)
                
                # --- ЗАПОЛНЕНИЕ ТАБЛИЦЫ ---
                cells = [item_date, item_type, item_title, item_status]
                for col_idx, item in enumerate(cells):
                    # Делаем ячейки только для чтения (как в остальном коде Dashboard)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(i, col_idx, item)
                    
        except Exception as e:
            logger.error(f"❌ Ошибка рендеринга центра уведомлений: {e}")
            
        finally:
            # 3. Возвращаем отрисовку обратно
            self.table.setUpdatesEnabled(True)

    def on_mark_read(self):
        row = self.table.currentRow()
        if row >= 0:
            notif_id = self.table.item(row, 2).data(Qt.UserRole)
            self.db_service.mark_notification_read(notif_id)
            self.refresh_data()

    def on_delete(self):
        row = self.table.currentRow()
        if row >= 0:
            notif_id = self.table.item(row, 2).data(Qt.UserRole)
            self.db_service.delete_notification(notif_id)
            self.refresh_data()


# ==============================================================================
# 🔑 ДИАЛОГ СМЕНЫ ПАРОЛЯ АДМИНИСТРАТОРА / СОТРУДНИКА
# ==============================================================================

class ChangePasswordDialog(QDialog):
    """Модальное окно для безопасной смены собственного пароля учетной записи."""

    def __init__(self, auth_service, db_service, user_data, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.db_service = db_service
        self.user_data = user_data

        self.setWindowTitle("Смена пароля учетной записи")
        self.setFixedSize(450, 320)
        self.setStyleSheet(load_stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(12)

        lbl_title = QLabel(f"Смена пароля: <b>{self.user_data.get('login', 'User')}</b>")
        lbl_title.setStyleSheet("font-size: 15px; color: #2E7D32;")
        layout.addWidget(lbl_title)

        form = QFormLayout()
        form.setSpacing(10)

        self.in_old = QLineEdit()
        self.in_old.setEchoMode(QLineEdit.Password)
        self.in_old.setPlaceholderText("Текущий пароль...")

        self.in_new = QLineEdit()
        self.in_new.setEchoMode(QLineEdit.Password)
        self.in_new.setPlaceholderText("Минимум 8 символов...")

        self.in_confirm = QLineEdit()
        self.in_confirm.setEchoMode(QLineEdit.Password)
        self.in_confirm.setPlaceholderText("Повторите новый пароль...")

        for inp in (self.in_old, self.in_new, self.in_confirm):
            inp.setMinimumHeight(38)

        form.addRow("Старый пароль:*", self.in_old)
        form.addRow("Новый пароль:*", self.in_new)
        form.addRow("Подтверждение:*", self.in_confirm)
        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.btn_save = QPushButton("💾 Сохранить новый пароль")
        self.btn_save.setMinimumHeight(42)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.handle_save)

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setMinimumHeight(42)
        self.btn_cancel.setObjectName("cancelButton")
        self.btn_cancel.clicked.connect(self.reject)

        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)

    def handle_save(self):
        old_pwd = self.in_old.text().strip()
        new_pwd = self.in_new.text().strip()
        confirm_pwd = self.in_confirm.text().strip()

        if not old_pwd or not new_pwd:
            QMessageBox.warning(self, "Внимание", "Заполните все обязательные поля!")
            return

        if len(new_pwd) < 8:
            QMessageBox.warning(self, "Внимание", "Новый пароль должен содержать не менее 8 символов!")
            return

        if new_pwd != confirm_pwd:
            QMessageBox.warning(self, "Внимание", "Новый пароль и подтверждение не совпадают!")
            return

        # Проверяем старый пароль по базе
        try:
            with self.db_service.get_cursor() as cur:
                cur.execute(
                    "SELECT password_hash FROM psychology.users WHERE id = %s::uuid;",
                    (str(self.user_data['id']),)
                )
                row = cur.fetchone()
                if not row or not self.auth_service.verify_password(old_pwd, row[0]):
                    QMessageBox.critical(self, "Отказ", "Текущий (старый) пароль введен неверно!")
                    return

            # Хешируем и обновляем пароль
            new_hash = self.auth_service.get_password_hash(new_pwd)
            self.db_service.change_user_password(str(self.user_data['id']), new_hash)

            QMessageBox.information(self, "Успех", "Пароль успешно обновлен!")
            self.accept()
        except Exception as e:
            logger.error(f"Password change error: {e}")
            QMessageBox.critical(self, "Ошибка БД", f"Не удалось изменить пароль:\n{e}")