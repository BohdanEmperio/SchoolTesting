#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
School Psychology Testing App - Test Taking Engine
============================================================
Модуль проведения тестирования (активный режим).
Senior Level: Безопасное сохранение ответов и контроль прогресса.
============================================================
"""

import json
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.services.scoring import score_selected_options

logger = logging.getLogger(__name__)


class TestTakingView(QDialog):
    """
    Модальное диалоговое окно последовательного прохождения тестирования.
    Обеспечивает изоляцию сессии, отображение вопросов и сохранение ответов.
    """

    def __init__(
        self,
        db_service: Any,
        test_id: str,
        test_name: str,
        student_id: Optional[str],
        parent: Optional[QDialog] = None,
    ):
        super().__init__(parent)
        self.db_service = db_service
        self.test_id = str(test_id)
        self.test_name = test_name
        self.student_id = str(student_id) if student_id else None

        self.questions: List[Dict[str, Any]] = []
        self.current_idx: int = 0
        self.session_id: Optional[str] = None
        self.choice_buttons: List[Any] = []
        self.choice_group = QButtonGroup(self)

        self.setWindowTitle(f"Выполнение: {test_name}")
        self.resize(850, 680)
        self.setMinimumSize(700, 520)

        # Блокируем закрытие на крестик, чтобы не прервать тест без сохранения
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        self.setup_ui()

        # Важно: Сначала загружаем данные, если не вышло — закрываем окно через event loop
        if not self.init_session_data():
            QTimer.singleShot(0, self.reject)

    def setup_ui(self) -> None:
        """📐 Отрисовка рабочего интерфейса тестирования."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Информационная панель прогресса
        self.progress_lbl = QLabel("Инициализация...")
        self.progress_lbl.setStyleSheet("color: #555; font-weight: bold;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(15)

        layout.addWidget(self.progress_lbl)
        layout.addWidget(self.progress_bar)

        # Контейнер для текста вопроса
        q_frame = QFrame()
        q_frame.setObjectName("questionBox")
        q_frame.setStyleSheet("""
            #questionBox {
                background: white; 
                border: 2px solid #4CAF50; 
                border-radius: 15px; 
            }
        """)
        f_layout = QVBoxLayout(q_frame)
        self.txt_display = QLabel("Ожидание данных из БД...")
        self.txt_display.setWordWrap(True)
        self.txt_display.setAlignment(Qt.AlignCenter)
        self.txt_display.setStyleSheet(
            "font-size: 20px; color: #333; font-weight: 500; border: none; padding: 20px;"
        )
        f_layout.addWidget(self.txt_display)
        layout.addWidget(q_frame)

        self.prompt_images_area = QScrollArea()
        self.prompt_images_area.setWidgetResizable(True)
        self.prompt_images_area.setMaximumHeight(190)
        self.prompt_images_widget = QWidget()
        self.prompt_images_layout = QHBoxLayout(self.prompt_images_widget)
        self.prompt_images_layout.setAlignment(Qt.AlignLeft)
        self.prompt_images_area.setWidget(self.prompt_images_widget)
        layout.addWidget(self.prompt_images_area)

        self.choices_area = QScrollArea()
        self.choices_area.setWidgetResizable(True)
        self.choices_widget = QWidget()
        self.choices_layout = QVBoxLayout(self.choices_widget)
        self.choices_area.setWidget(self.choices_widget)
        layout.addWidget(self.choices_area)

        # Кнопки взаимодействия
        self.legacy_buttons_widget = QWidget()
        self.nav_layout = QHBoxLayout(self.legacy_buttons_widget)
        self.nav_layout.setSpacing(20)

        self.btn_yes = QPushButton("ДА (Полностью согласен)")
        self.btn_yes.setMinimumHeight(65)
        self.btn_yes.setCursor(Qt.PointingHandCursor)
        self.btn_yes.setStyleSheet(
            "background: #2E7D32; color: white; font-size: 16px; font-weight: bold; border-radius: 10px;"
        )
        self.btn_yes.clicked.connect(lambda: self.on_answer_submitted(1))

        self.btn_no = QPushButton("НЕТ (Не согласен)")
        self.btn_no.setMinimumHeight(65)
        self.btn_no.setCursor(Qt.PointingHandCursor)
        self.btn_no.setStyleSheet(
            "background: #C62828; color: white; font-size: 16px; font-weight: bold; border-radius: 10px;"
        )
        self.btn_no.clicked.connect(lambda: self.on_answer_submitted(0))

        self.nav_layout.addWidget(self.btn_yes)
        self.nav_layout.addWidget(self.btn_no)
        layout.addWidget(self.legacy_buttons_widget)

        self.btn_submit_choices = QPushButton("Сохранить выбор и продолжить")
        self.btn_submit_choices.setMinimumHeight(48)
        self.btn_submit_choices.clicked.connect(self.on_choice_submitted)
        layout.addWidget(self.btn_submit_choices)

        self.prompt_images_area.hide()
        self.choices_area.hide()
        self.btn_submit_choices.hide()

    def init_session_data(self) -> bool:
        """🔑 Синхронная подготовка данных сессии."""
        try:
            # 1. Проверяем наличие ученика
            if not self.student_id:
                QMessageBox.critical(
                    self,
                    "Ошибка профиля",
                    "Ваша учетная запись не привязана к базе учеников. Обратитесь к психологу.",
                )
                return False

            # 2. Создаем сессию в БД
            self.session_id = str(
                self.db_service.create_test_session(self.student_id, self.test_id)
            )

            # 3. Загружаем вопросы
            self.questions = self.db_service.get_full_test_questions(self.test_id)

            if not self.questions:
                QMessageBox.warning(
                    self,
                    "Пустая методика",
                    "В выбранном тесте нет активных вопросов.",
                )
                return False

            # Устанавливаем лимит прогресс-бара
            self.progress_bar.setMaximum(len(self.questions))
            self.update_question_on_screen()
            return True

        except Exception as e:
            logger.error(f"Сбой инициализации теста: {e}")
            QMessageBox.critical(
                self, "Ошибка БД", f"Не удалось запустить тест: {str(e)}"
            )
            return False

    def update_question_on_screen(self) -> None:
        """🖼️ Отрисовка текущего вопроса."""
        if self.current_idx < len(self.questions):
            q_data = self.questions[self.current_idx]
            current_text = str(q_data["text"])

            self.txt_display.setText(current_text)
            self.progress_bar.setValue(self.current_idx + 1)
            self.progress_lbl.setText(
                f"Вопрос {self.current_idx + 1} из {len(self.questions)}"
            )
            options_data = self._parse_options(q_data.get("options"))
            options = options_data.get("options") if isinstance(options_data, dict) else None
            self._render_question_images(q_data)
            if isinstance(options, list):
                self.legacy_buttons_widget.hide()
                self.choices_area.show()
                self.btn_submit_choices.show()
                self._render_choices(q_data, options_data, options)
            else:
                self.legacy_buttons_widget.show()
                self.choices_area.hide()
                self.btn_submit_choices.hide()
                self._clear_layout(self.choices_layout)
                self.prompt_images_area.hide()
        else:
            # Если вопросы кончились — рассчитываем и сохраняем результат
            self.finish_testing()

    @staticmethod
    def _parse_options(raw_options: Any) -> Dict[str, Any]:
        if isinstance(raw_options, str):
            return json.loads(raw_options)
        return raw_options if isinstance(raw_options, dict) else {}

    @staticmethod
    def _clear_layout(layout: QVBoxLayout | QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _render_question_images(self, question: Dict[str, Any]) -> None:
        self._clear_layout(self.prompt_images_layout)
        media_content = question.get("media_content") or {}
        if isinstance(media_content, str):
            media_content = json.loads(media_content)
        prompt_keys = set(media_content.get("prompt_images", []))
        assets = {
            str(asset["key"]): asset
            for asset in question.get("media_assets", [])
        }
        for media_key in media_content.get("prompt_images", []):
            asset = assets.get(str(media_key))
            if asset:
                self.prompt_images_layout.addWidget(
                    self._image_widget(asset, "Рисунок к заданию")
                )
        self.prompt_images_area.setVisible(bool(prompt_keys))

    @staticmethod
    def _image_widget(asset: Dict[str, Any], fallback: str) -> QLabel:
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap()
        if pixmap.loadFromData(bytes(asset["data"])):
            label.setPixmap(pixmap.scaled(250, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logger.error("Не удалось отобразить изображение %s", asset.get("file_name"))
            label.setText(fallback + "\n[изображение недоступно]")
        label.setToolTip(str(asset.get("file_name", fallback)))
        return label

    def _render_choices(
        self,
        question: Dict[str, Any],
        options_data: Dict[str, Any],
        options: List[Dict[str, Any]],
    ) -> None:
        self._clear_layout(self.choices_layout)
        for button in self.choice_group.buttons():
            self.choice_group.removeButton(button)
        self.choice_buttons.clear()

        assets = {
            str(asset["key"]): asset
            for asset in question.get("media_assets", [])
        }
        multiple = options_data.get("selection_mode") == "multiple"
        self.choice_group.setExclusive(not multiple)

        for option in options:
            option_id = str(option.get("id", ""))
            text = str(option.get("text", ""))
            asset = assets.get(str(option.get("media_key", "")))
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            if multiple:
                button = QCheckBox(text)
            else:
                button = QRadioButton(text)
                self.choice_group.addButton(button)
            button.setProperty("option_id", option_id)
            button.setProperty("option", option)
            self.choice_buttons.append(button)
            row_layout.addWidget(button)
            if asset:
                row_layout.addWidget(self._image_widget(asset, text or "Вариант ответа"))
            row_layout.addStretch()
            self.choices_layout.addWidget(row_widget)
        self.choices_layout.addStretch()

    @Slot(int)
    def on_answer_submitted(self, value: int) -> None:
        """
        💾 Сохранение выбора с учетом весов (баллов), прописанных в методике.
        value: 1 приходит при нажатии кнопки 'ДА', 0 при нажатии кнопки 'НЕТ'.
        """
        try:
            current_q = self.questions[self.current_idx]
            q_id = str(current_q["id"])
            q_text = str(current_q["text"])
            q_order = int(current_q["order"])
            choice_text = "Да" if value == 1 else "Нет"
            weights: Dict[str, Any] = {"Да": 1, "Нет": 0}
            parsed_options = self._parse_options(current_q.get("options"))
            if "options" in parsed_options:
                raise ValueError(
                    "Для вопроса с вариантами ответа отображены кнопки Да/Нет."
                )
            weights.update(parsed_options)
            real_points = float(weights.get(choice_text, 1.0 if value == 1 else 0.0))
            self._save_current_answer(
                current_q,
                real_points,
                choice_text,
                {"choice": choice_text, "value": int(value)},
            )
        except Exception as e:
            logger.error(f"Критический сбой сохранения ответа: {e}")
            QMessageBox.warning(
                self,
                "Ошибка связи",
                "Ваш выбор не зафиксирован в БД. Попробуйте еще раз.",
            )

    @Slot()
    def on_choice_submitted(self) -> None:
        """Save one or more selected answer options and their summed score."""
        current_q = self.questions[self.current_idx]
        selected = [button.property("option") for button in self.choice_buttons if button.isChecked()]
        if not selected:
            QMessageBox.warning(
                self, "Не выбран ответ", "Выберите хотя бы один вариант ответа."
            )
            return

        try:
            selected_ids = [str(option["id"]) for option in selected]
            options_data = self._parse_options(
                current_q.get("options")
            )
            score = score_selected_options(
                options_data["options"],
                selected_ids,
            )
            selected_labels = [
                str(option.get("text") or f"Вариант {index + 1}")
                for index, option in enumerate(selected)
            ]
            self._save_current_answer(
                current_q,
                score,
                ", ".join(selected_labels),
                {
                    "selected_option_ids": selected_ids,
                    "selected_options": selected_labels,
                    "value": score,
                },
            )
        except (KeyError, TypeError, ValueError) as error:
            logger.error("Некорректный выбор в задании: %s", error)
            QMessageBox.warning(
                self, "Ошибка ответа", f"Не удалось сохранить выбранный вариант: {error}"
            )

    def _save_current_answer(
        self,
        question: Dict[str, Any],
        points: float,
        choice_text: str,
        answer_data: Dict[str, Any],
    ) -> None:
        self.db_service.save_answer(
            sess_id=self.session_id,
            q_num=int(question["order"]),
            point_val=points,
            q_id=str(question["id"]),
            choice_text=choice_text,
            q_text=str(question["text"]),
            q_type=str(question["question_type"]),
            answer_data=answer_data,
        )
        logger.debug(
            "Ответ сохранен для вопроса %s; начислено %.3f балла.",
            question["order"],
            points,
        )
        self.current_idx += 1
        self.update_question_on_screen()

    def finish_testing(self) -> None:
        """🏆 Итоговый расчет и завершение сессии."""
        try:
            # Блокируем кнопки, чтобы исключить повторные клики
            self.btn_yes.setEnabled(False)
            self.btn_no.setEnabled(False)
            self.btn_submit_choices.setEnabled(False)

            # Финализация теста в БД
            if hasattr(self.db_service, "finalize_test_and_calculate"):
                self.db_service.finalize_test_and_calculate(self.session_id, self.test_id)

            QMessageBox.information(
                self,
                "Успешно",
                "Поздравляем! Вы завершили тестирование.\n"
                "Результат направлен вашему школьному психологу.",
            )
            self.accept()

        except Exception as e:
            logger.error(f"Ошибка при финальном расчете: {e}")
            QMessageBox.critical(
                self,
                "Завершение",
                f"Тест закончен, но возникла ошибка при расчете: {e}",
            )
            self.accept()