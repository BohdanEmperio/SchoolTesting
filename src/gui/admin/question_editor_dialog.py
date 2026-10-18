"""Editor for a methodology question and its optional picture assets."""

import json
import logging
import math
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class QuestionEditorDialog(QDialog):
    """Configure a question, choice scoring, and images stored in PostgreSQL."""

    def __init__(
        self,
        question: Optional[Dict[str, Any]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Задание и варианты ответа")
        self.resize(820, 620)
        self.question = question or {}
        self.assets: Dict[str, Dict[str, Any]] = {
            str(asset["key"]): dict(asset)
            for asset in self.question.get("media_assets", [])
        }
        self.prompt_keys: List[str] = []
        self.option_ids: List[str] = []
        self._build_ui()
        self._load_question()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.question_text = QLineEdit()
        self.question_text.setPlaceholderText("Введите формулировку задания")
        form.addRow("Текст задания:", self.question_text)

        self.selection_mode = QComboBox()
        self.selection_mode.addItem("Выбрать один вариант", "single")
        self.selection_mode.addItem("Выбрать несколько вариантов", "multiple")
        form.addRow("Режим выбора:", self.selection_mode)
        layout.addLayout(form)

        prompt_header = QHBoxLayout()
        prompt_header.addWidget(QLabel("Рисунки к заданию:"))
        prompt_header.addStretch()
        add_prompt_button = QPushButton("Добавить рисунок")
        add_prompt_button.clicked.connect(self._add_prompt_image)
        remove_prompt_button = QPushButton("Удалить выбранный")
        remove_prompt_button.clicked.connect(self._remove_prompt_image)
        prompt_header.addWidget(add_prompt_button)
        prompt_header.addWidget(remove_prompt_button)
        layout.addLayout(prompt_header)

        self.prompt_images = QListWidget()
        self.prompt_images.setMaximumHeight(110)
        layout.addWidget(self.prompt_images)

        options_header = QHBoxLayout()
        options_header.addWidget(QLabel("Варианты ответа и баллы:"))
        options_header.addStretch()
        add_option_button = QPushButton("Добавить вариант")
        add_option_button.clicked.connect(self._add_option)
        options_header.addWidget(add_option_button)
        layout.addLayout(options_header)

        self.options_table = QTableWidget(0, 5)
        self.options_table.setHorizontalHeaderLabels(
            ["Текст варианта", "Баллы", "Рисунок варианта", "Очистить рисунок", "Удалить"]
        )
        self.options_table.horizontalHeader().setStretchLastSection(False)
        self.options_table.setColumnWidth(0, 240)
        self.options_table.setColumnWidth(1, 85)
        self.options_table.setColumnWidth(2, 180)
        self.options_table.setColumnWidth(3, 120)
        self.options_table.setColumnWidth(4, 80)
        layout.addWidget(self.options_table)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_question(self) -> None:
        self.question_text.setText(str(self.question.get("text", "")))

        options_data = self.question.get("options", {})
        if isinstance(options_data, str):
            options_data = json.loads(options_data)

        if isinstance(options_data, dict) and isinstance(
            options_data.get("options"), list
        ):
            choices = options_data["options"]
            mode = options_data.get("selection_mode", "single")
        elif isinstance(options_data, dict):
            choices = [
                {"id": uuid.uuid4().hex, "text": label, "value": value}
                for label, value in options_data.items()
            ]
            mode = (
                "multiple"
                if self.question.get("question_type") == "multiple_choice"
                else "single"
            )
        elif isinstance(options_data, list):
            choices = options_data
            mode = "single"
        else:
            choices = []
            mode = "single"

        selected_index = self.selection_mode.findData(mode)
        self.selection_mode.setCurrentIndex(max(selected_index, 0))

        media_content = self.question.get("media_content", {}) or {}
        if isinstance(media_content, str):
            media_content = json.loads(media_content)
        self.prompt_keys = [
            str(key) for key in media_content.get("prompt_images", [])
        ]
        for key in self.prompt_keys:
            asset = self.assets.get(key)
            if asset:
                self._append_prompt_item(key, asset["file_name"])

        for choice in choices:
            option_id = str(choice.get("id") or uuid.uuid4().hex)
            self._append_option(
                option_id=option_id,
                text=str(choice.get("text", "")),
                score=str(choice.get("value", choice.get("score", 0))),
                media_key=choice.get("media_key"),
            )

        if not choices:
            self._append_option()
            self._append_option()

    def _append_prompt_item(self, key: str, file_name: str) -> None:
        from PySide6.QtWidgets import QListWidgetItem

        item = QListWidgetItem(file_name)
        item.setData(Qt.UserRole, key)
        self.prompt_images.addItem(item)

    @staticmethod
    def _read_image(file_path: str) -> Optional[Dict[str, Any]]:
        suffix = Path(file_path).suffix.lower()
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }.get(suffix)
        if not mime_type:
            QMessageBox.warning(
                None,
                "Формат изображения",
                "Поддерживаются только изображения PNG и JPEG.",
            )
            return None

        reader = QImageReader(file_path)
        if not reader.canRead():
            QMessageBox.warning(
                None,
                "Некорректное изображение",
                f"Не удалось прочитать файл: {Path(file_path).name}",
            )
            return None

        try:
            file_data = Path(file_path).read_bytes()
        except OSError as error:
            logger.error("Не удалось прочитать изображение %s: %s", file_path, error)
            QMessageBox.critical(
                None, "Ошибка файла", f"Не удалось прочитать изображение:\n{error}"
            )
            return None

        if not file_data:
            QMessageBox.warning(None, "Пустой файл", "Выбранный файл пуст.")
            return None

        return {
            "key": uuid.uuid4().hex,
            "file_name": Path(file_path).name,
            "mime_type": mime_type,
            "data": file_data,
        }

    def _choose_image_file(self) -> Optional[Dict[str, Any]]:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите рисунок",
            "",
            "Изображения (*.png *.jpg *.jpeg)",
        )
        return self._read_image(file_path) if file_path else None

    def _add_prompt_image(self) -> None:
        asset = self._choose_image_file()
        if not asset:
            return
        asset["role"] = "prompt"
        asset["option_id"] = None
        self.assets[asset["key"]] = asset
        self.prompt_keys.append(asset["key"])
        self._append_prompt_item(asset["key"], asset["file_name"])

    def _remove_prompt_image(self) -> None:
        item = self.prompt_images.currentItem()
        if not item:
            return
        key = str(item.data(Qt.UserRole))
        self.prompt_keys = [existing for existing in self.prompt_keys if existing != key]
        self.prompt_images.takeItem(self.prompt_images.row(item))

    def _append_option(
        self,
        option_id: Optional[str] = None,
        text: str = "",
        score: str = "0",
        media_key: Optional[str] = None,
    ) -> None:
        option_id = option_id or uuid.uuid4().hex
        row = self.options_table.rowCount()
        self.options_table.insertRow(row)
        self.option_ids.append(option_id)
        self.options_table.setItem(row, 0, QTableWidgetItem(text))
        self.options_table.setItem(row, 1, QTableWidgetItem(score))
        self._set_option_image_button(row, option_id, media_key)

        clear_button = QPushButton("Очистить")
        clear_button.clicked.connect(
            lambda checked=False, current_id=option_id: self._clear_option_image(
                current_id
            )
        )
        self.options_table.setCellWidget(row, 3, clear_button)

        delete_button = QPushButton("Удалить")
        delete_button.clicked.connect(
            lambda checked=False, current_id=option_id: self._remove_option(current_id)
        )
        self.options_table.setCellWidget(row, 4, delete_button)

    def _set_option_image_button(
        self, row: int, option_id: str, media_key: Optional[str]
    ) -> None:
        asset = self.assets.get(str(media_key)) if media_key else None
        button = QPushButton(asset["file_name"] if asset else "Выбрать…")
        button.clicked.connect(
            lambda checked=False, current_id=option_id: self._choose_option_image(
                current_id
            )
        )
        self.options_table.setCellWidget(row, 2, button)
        self.options_table.item(row, 0).setData(
            Qt.UserRole, str(media_key) if media_key else None
        )

    def _add_option(self) -> None:
        self._append_option()

    def _remove_option(self, option_id: str) -> None:
        if len(self.option_ids) <= 2:
            QMessageBox.warning(
                self, "Варианты ответа", "У задания должно быть не менее двух вариантов."
            )
            return
        row = self.option_ids.index(option_id)
        self.option_ids.pop(row)
        self.options_table.removeRow(row)

    def _choose_option_image(self, option_id: str) -> None:
        asset = self._choose_image_file()
        if not asset:
            return
        asset["role"] = "option"
        asset["option_id"] = option_id
        self.assets[asset["key"]] = asset
        row = self.option_ids.index(option_id)
        self._set_option_image_button(row, option_id, asset["key"])

    def _clear_option_image(self, option_id: str) -> None:
        row = self.option_ids.index(option_id)
        old_key = self.options_table.item(row, 0).data(Qt.UserRole)
        if old_key:
            self.assets.pop(str(old_key), None)
        self._set_option_image_button(row, option_id, None)

    def _validate_and_accept(self) -> None:
        if not self.question_text.text().strip():
            QMessageBox.warning(self, "Задание", "Введите текст задания.")
            return
        if self.options_table.rowCount() < 2:
            QMessageBox.warning(
                self, "Варианты ответа", "Добавьте не менее двух вариантов."
            )
            return

        for row in range(self.options_table.rowCount()):
            text_item = self.options_table.item(row, 0)
            score_item = self.options_table.item(row, 1)
            label = text_item.text().strip() if text_item else ""
            image_key = text_item.data(Qt.UserRole) if text_item else None
            if not label and not image_key:
                QMessageBox.warning(
                    self,
                    "Вариант ответа",
                    f"Вариант №{row + 1} должен иметь текст или рисунок.",
                )
                return
            try:
                score = float((score_item.text() if score_item else "0").replace(",", "."))
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Баллы",
                    f"Укажите числовое значение баллов для варианта №{row + 1}.",
                )
                return
            if not math.isfinite(score) or score < 0:
                QMessageBox.warning(
                    self,
                    "Баллы",
                    "Укажите конечное неотрицательное значение баллов.",
                )
                return
        self.accept()

    def get_question_data(self) -> Dict[str, Any]:
        """Return validated question and image data ready for persistence."""
        choices: List[Dict[str, Any]] = []
        media_assets: List[Dict[str, Any]] = []
        prompt_images = set(self.prompt_keys)

        for row, option_id in enumerate(self.option_ids):
            text_item = self.options_table.item(row, 0)
            score_item = self.options_table.item(row, 1)
            text = text_item.text().strip() if text_item else ""
            media_key = text_item.data(Qt.UserRole) if text_item else None
            if not text:
                text = f"Вариант {row + 1}"
            score = float(
                (score_item.text() if score_item else "0").replace(",", ".")
            )
            choice = {
                "id": option_id,
                "text": text,
                "value": score,
            }
            if media_key:
                choice["media_key"] = str(media_key)
            choices.append(choice)

        for key, asset in self.assets.items():
            if key in prompt_images or any(
                choice.get("media_key") == key for choice in choices
            ):
                media_assets.append(dict(asset))

        selection_mode = str(self.selection_mode.currentData())
        has_images = bool(media_assets)
        question_type = (
            "multiple_choice"
            if selection_mode == "multiple"
            else "image_choice"
            if has_images
            else "single_choice"
        )
        return {
            "text": self.question_text.text().strip(),
            "question_type": question_type,
            "options": {
                "selection_mode": selection_mode,
                "options": choices,
            },
            "media_content": {"prompt_images": list(self.prompt_keys)},
            "media_assets": media_assets,
        }
