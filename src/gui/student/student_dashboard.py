#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
School Psychology Testing App - Student Dashboard
============================================================
Компонент: Личный кабинет учащегося.
Функционал: Просмотр профиля, доступных тестов и истории.
============================================================
"""

import logging
import traceback
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.student.test_taking_view import TestTakingView
from src.gui.styles.live_reload import load_stylesheet
from src.services.students_service import StudentsService

# Настройка логгера для текущего модуля
logger = logging.getLogger(__name__)


class StudentDashboard(QWidget):
    """
    Интерфейс личного кабинета ученика.
    Позволяет просматривать доступные тесты и историю прохождений.
    """

    def __init__(self, auth_service, db_service, user_data: dict, parent=None):
        """
        Инициализация кабинета.
        
        :param auth_service: Сервис аутентификации.
        :param db_service: Сервис взаимодействия с базой данных.
        :param user_data: Словарь с данными авторизованного пользователя.
        """
        super().__init__(parent)
        self.auth_service = auth_service
        self.db_service = db_service
        self.students_service = StudentsService(db_service)
        self.user_data = user_data

        # Инициализация ссылок на UI элементы
        self.tests_table: Optional[QTableWidget] = None
        self.results_table: Optional[QTableWidget] = None
        self.profile_label: Optional[QLabel] = None
        self.header_label: Optional[QLabel] = None

        # Установка стилей и построение интерфейса
        self.setStyleSheet(load_stylesheet())
        self.setup_ui()
        
        # Первичная загрузка данных
        self.refresh_dashboard_data()

    def setup_ui(self):
        """⚙️ Настройка графической структуры окна."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(25)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # --- ВЕРХНИЙ БЛОК (ПРИВЕТСТВИЕ) ---
        self.header_label = QLabel("Загрузка данных...")
        self.header_label.setObjectName("title")
        main_layout.addWidget(self.header_label)

        # --- ТАБ-ВИДЖЕТ ---
        self.tabs = QTabWidget()
        
        # Наполнение вкладок
        self.tabs.addTab(self._create_tests_tab(), "📝 Доступные тесты")
        self.tabs.addTab(self._create_results_tab(), "📊 Мои результаты")
        self.tabs.addTab(self._create_profile_tab(), "👤 Профиль")

        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    # ============================================================
    # 📝 ВКЛАДКА 1: ДОСТУПНЫЕ ТЕСТЫ
    # ============================================================
    def _create_tests_tab(self) -> QWidget:
        """Создает страницу со списком актуальных тестов."""
        container = QWidget()
        layout = QVBoxLayout(container)
        
        sub_info = QLabel("Выберите диагностическую методику из списка ниже:")
        sub_info.setObjectName("subtitle")
        layout.addWidget(sub_info)

        # Таблица: (UUID скрыт, Название, Количество вопросов)
        self.tests_table = QTableWidget(0, 3)
        self.tests_table.setHorizontalHeaderLabels(["ID", "Название методики", "Объем"])
        self.tests_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tests_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.tests_table.hideColumn(0)  # Скрываем UUID от пользователя
        
        layout.addWidget(self.tests_table)

        self.btn_start = QPushButton("🚀 Начать тестирование")
        self.btn_start.setMinimumHeight(60)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        # Применяем акцентный стиль (зеленый)
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 16px;")
        self.btn_start.clicked.connect(self.on_start_test_clicked)
        
        layout.addWidget(self.btn_start)
        return container

    # ============================================================
    # 📊 ВКЛАДКА 2: ИСТОРИЯ РЕЗУЛЬТАТОВ
    # ============================================================
    def _create_results_tab(self) -> QWidget:
        """Создает страницу архива завершенных сессий."""
        container = QWidget()
        layout = QVBoxLayout(container)
        
        info = QLabel("История ваших завершенных диагностик:")
        info.setObjectName("subtitle")
        layout.addWidget(info)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Методика", "Результат (балл)", "Заключение", "Дата"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.results_table)
        return container

    # ============================================================
    # 👤 ВКЛАДКА 3: КАРТОЧКА ПРОФИЛЯ
    # ============================================================
    def _create_profile_tab(self) -> QWidget:
        """Создает страницу информации об ученике."""
        container = QWidget()
        layout = QVBoxLayout(container)
        
        profile_card = QWidget()
        profile_card.setStyleSheet("background: white; border: 1px solid #ddd; border-radius: 12px; padding: 25px;")
        card_layout = QVBoxLayout(profile_card)

        self.profile_label = QLabel("Считывание личных данных...")
        self.profile_label.setStyleSheet("font-size: 16px; line-height: 1.8;")
        self.profile_label.setWordWrap(True)
        
        card_layout.addWidget(self.profile_label)
        layout.addWidget(profile_card)
        
        # Блок кнопок внизу профиля
        bottom_layout = QHBoxLayout()
        logout_btn = QPushButton("🚪 Выйти из кабинета")
        logout_btn.setMinimumHeight(45)
        logout_btn.setFixedWidth(220)
        # ✅ Исправлено: QApplication.instance().activeWindow() может быть None в некоторых ОС, 
        # безопаснее закрывать виджет через self.parent() или прямое обращение
        logout_btn.clicked.connect(self._handle_logout)
        
        bottom_layout.addWidget(logout_btn)
        bottom_layout.addStretch()
        layout.addLayout(bottom_layout)

        layout.addStretch()
        return container

    # ============================================================
    # 🧠 БИЗНЕС-ЛОГИКА И ОБРАБОТКА ДАННЫХ
    # ============================================================

    def _safe_decode_bytes(self, value: any) -> str:
        """Senior-логика декодирования. Обрабатывает и чистые байты, и строки-экраны."""
        if value is None:
            return ""
        try:
            # Если пришел memoryview (норма для psycopg2 и BYTEA)
            if hasattr(value, "tobytes"):
                return value.tobytes().decode("utf-8")
            # Если пришла строка, которая выглядит как octal (типа \320\230)
            if isinstance(value, str) and "\\" in value:
                # Магия: превращаем строку 'octal-escape' обратно в нормальные байты
                return value.encode('latin1').decode('unicode_escape').encode('latin1').decode('utf-8')
            return str(value)
        except Exception as e:
            logger.warning(f"Ошибка декодирования: {e}")
            return "---"

    def refresh_dashboard_data(self) -> None:
        """
        🚀 Глобальная синхронизация интерфейса кабинета с актуальными данными БД.
        Реализована Senior-логика разделения данных: сбой в одном блоке не ломает другие.
        """
        user_uuid = self.user_data.get("id")
        student_id = self.user_data.get("student_id")
        
        logger.info(f"Синхронизация личного кабинета пользователя ID: {user_uuid}")

        # --- БЛОК 1: ИДЕНТИФИКАЦИЯ И ПРИВЕТСТВИЕ ---
        try:
            profile = self.students_service.get_student_profile(user_uuid)
            if profile:
                # profile возвращает: (first_name_enc, last_name_enc, class_name)
                # Безопасное декодирование для исключения ошибок кодировки
                first_name = self._safe_decode_bytes(profile[0])
                last_name = self._safe_decode_bytes(profile[1])
                class_name = profile[2] if profile[2] else "Класс не указан"

                self.header_label.setText(f"👋 Приветствуем, {first_name} {last_name}!")
                
                info_content = (
                    f"<b>🎓 Личная информация:</b><br><br>"
                    f"▪️ <b>Ученик:</b> {last_name} {first_name}<br>"
                    f"▪️ <b>Группа обучения:</b> {class_name}<br>"
                    f"▪️ <b>Системный логин:</b> {self.user_data.get('login')}<br>"
                    f"▪️ <b>Состояние доступа:</b> Профиль синхронизирован"
                )
                self.profile_label.setText(info_content)
                logger.debug("Данные профиля обновлены.")
            else:
                self.header_label.setText("👋 Добро пожаловать!")

        except Exception as profile_err:
            logger.error(f"❌ Ошибка формирования профиля: {profile_err}")
            self.header_label.setText("👋 Кабинет ученика")

        # --- БЛОК 2: СПИСОК ДОСТУПНЫХ МЕТОДИК ---
        try:
            available_tests = self.db_service.get_available_tests()
            
            self.tests_table.setRowCount(0)
            if available_tests:
                for row_idx, test_data in enumerate(available_tests):
                    self.tests_table.insertRow(row_idx)
                    
                    # (0: ID, 1: Название, 2: Вопросы)
                    id_item = QTableWidgetItem(str(test_data[0]))
                    name_item = QTableWidgetItem(str(test_data[1]))
                    count_item = QTableWidgetItem(f"{test_data[2]} вопр.")
                    
                    # Делаем данные только для чтения
                    for item in [id_item, name_item, count_item]:
                        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

                    self.tests_table.setItem(row_idx, 0, id_item)
                    self.tests_table.setItem(row_idx, 1, name_item)
                    self.tests_table.setItem(row_idx, 2, count_item)
            else:
                logger.info("Доступные тесты не найдены.")

        except Exception as test_err:
            logger.error(f"❌ Ошибка загрузки тестов: {test_err}")
            QMessageBox.critical(self, "Ошибка БД", "Не удалось загрузить доступные тесты.")

        # --- БЛОК 3: ЛИЧНЫЙ АРХИВ РЕЗУЛЬТАТОВ (С РАСКРАСКОЙ) ---
        if student_id and str(student_id) != "None":
            try:
                # Ожидаем: (test_name, overall_score, risk_level, summary_text, created_at)
                history_data = self.db_service.get_student_results(student_id)
                self.results_table.setRowCount(0)
                
                if history_data:
                    for row_idx, res in enumerate(history_data):
                        self.results_table.insertRow(row_idx)
                        
                        # 0. Название методики
                        self.results_table.setItem(row_idx, 0, QTableWidgetItem(str(res[0])))
                        
                        # 1. Результат (числовой балл)
                        score_item = QTableWidgetItem(str(res[1]))
                        score_item.setTextAlignment(Qt.AlignCenter)
                        self.results_table.setItem(row_idx, 1, score_item)
                        
                        # 2. Логика Заключения (res[2]) + Текст (res[3]) + Раскраска
                        risk_level_str = str(res[2]) # "Низкий", "Средний", "Высокий" или "Норма"
                        conc_item = QTableWidgetItem(risk_level_str)
                        
                        # ✨ Senior: Применяем цветовую кодировку в зависимости от статуса
                        if "Высокий" in risk_level_str:
                            conc_item.setForeground(Qt.red) # Критический риск
                        elif "Средний" in risk_level_str:
                            conc_item.setForeground(Qt.blue) # Требует внимания
                        elif "Норма" in risk_level_str or "Низкий" in risk_level_str:
                            conc_item.setForeground(Qt.darkGreen) # Благоприятно
                        
                        # Детальное описание прячем в Tooltip (всплывающая подсказка)
                        # res[3] - это наш большой текст summary из DatabaseService
                        conc_item.setToolTip(f"<b>АНАЛИТИЧЕСКИЙ ОТЧЕТ:</b><br><br>{str(res[3])}")
                        self.results_table.setItem(row_idx, 2, conc_item)
                        
                        # 4. Дата прохождения (Берем первые 16 символов даты-времени)
                        # Защита от IndexError если SQL вернул меньше полей
                        date_str = "---"
                        if len(res) > 4 and res[4]:
                            date_str = str(res[4])[:16]
                            
                        self.results_table.setItem(row_idx, 3, QTableWidgetItem(date_str))
                    
                    self.results_table.resizeRowsToContents()
                else:
                    logger.info("Архив результатов пуст.")

            except Exception as history_err:
                logger.error(f"❌ Ошибка визуализации результатов: {history_err}")
                traceback.print_exc()
        else:
            logger.warning("Синхронизация истории невозможна: student_id отсутствует.")

        # Очистка очереди событий для предотвращения зависания GUI при больших таблицах
        QApplication.processEvents()
            
            
    def _handle_logout(self):
        """Метод выхода: закрывает текущее окно приложения."""
        logger.info(f"Ученик {self.user_data.get('login')} вышел из системы.")
        # ✅ Senior стиль: обращение к основному окну через инстанс
        main_win = QApplication.activeWindow()
        if main_win:
            main_win.close()

    @Slot()
    def on_start_test_clicked(self) -> None:
        """
        🚀 Инициализация запуска тестирования (Senior V8.2).
        Последовательность: Выбор -> Загрузка структуры -> Инструктаж -> Тестирование.
        """
        # 1. Получаем индекс выделенной строки
        row = self.tests_table.currentRow()
        
        if row < 0:
            QMessageBox.warning(self, "Выбор методики", "Пожалуйста, выделите тест в таблице.")
            return

        # Получаем ID теста из скрытой первой колонки
        test_id_str = self.tests_table.item(row, 0).text()
        
        try:
            # 2. Извлекаем расширенную структуру теста (вопросы, шкалы, мета-данные)
            # В DatabaseService этот метод теперь возвращает (questions, scales, meta_dict)
            _, _, meta = self.db_service.get_test_full_structure(test_id_str)
            
            # 3. Визуализация окна вводного инструктажа (Intro)
            intro_dialog = TestIntroDialog(
                test_name=meta.get('name', 'Диагностическая методика'),
                description=meta.get('desc', 'Описание в процессе подготовки.'),
                instructions=meta.get('instructions', 'Следуйте подсказкам системы.'),
                parent=self
            )
            
            # Если ученик ознакомился и нажал "Начать тест"
            if intro_dialog.exec() == QDialog.Accepted:
                # 4. Получаем ID ученика и запускаем движок вопросов
                stud_id = self.user_data.get('student_id')
                
                test_engine = TestTakingView(
                    db_service=self.db_service, 
                    test_id=test_id_str, 
                    test_name=meta.get('name', 'Тест'), 
                    student_id=stud_id, 
                    parent=self
                )
                
                # По завершении (нажат финиш) обновляем результаты в кабинете
                if test_engine.exec() == QDialog.Accepted:
                    logger.info(f"Тест успешно завершен пользователем {self.user_data.get('login')}")
                    self.refresh_dashboard_data()
                    
        except Exception as e:
            logger.error(f"🚨 Сбой инициализации сессии теста: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка БД", f"Не удалось подготовить тест: {str(e)}")
            

class TestIntroDialog(QDialog):
    """Окно-превью теста с инструкцией."""
    def __init__(self, test_name, description, instructions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Инструкция к тесту")
        self.setFixedWidth(600)
        self.setStyleSheet(load_stylesheet())
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        title = QLabel(test_name)
        title.setObjectName("title")
        title.setWordWrap(True)
        
        desc = QLabel(f"<b>О тесте:</b><br>{description}")
        desc.setWordWrap(True)
        
        instr_box = QWidget()
        instr_box.setStyleSheet("background-color: #E3F2FD; border-left: 5px solid #2196F3; padding: 10px;")
        instr_lay = QVBoxLayout(instr_box)
        instr_lay.addWidget(QLabel("📖 <b>ИНСТРУКЦИЯ:</b>"))
        instr_text = QLabel(instructions)
        instr_text.setWordWrap(True)
        instr_lay.addWidget(instr_text)
        
        layout.addWidget(title)
        layout.addWidget(desc)
        layout.addWidget(instr_box)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Начать тест")
        btns.button(QDialogButtonBox.Cancel).setText("Отмена")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)