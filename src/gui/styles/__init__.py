#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# src/gui/styles/__init__.py

"""
🎨 Глобальные стили приложения (QSS)
Здесь настраивается визуальная составляющая всех компонентов.
"""

STYLESHEET = """
/* 1. Общие настройки для всех окон */
QWidget {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 14px;
    background-color: #f8f9fa; /* Светлый современный фон */
    color: #333333;
}

/* 2. Заголовки (через ObjectName) */
QLabel#title {
    font-size: 26px;
    font-weight: bold;
    color: #2e7d32; /* Тёмно-зеленый */
    margin-bottom: 5px;
}

QLabel#subtitle {
    font-size: 15px;
    color: #666666;
}

/* 3. Кнопки (современный скругленный вид) */
QPushButton {
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 8px; /* Более мягкие углы */
    padding: 10px 20px;
    font-size: 15px;
    font-weight: bold;
    min-height: 25px;
}

QPushButton:hover {
    background-color: #45a049;
}

QPushButton:pressed {
    background-color: #3d8b40;
}

QPushButton:disabled {
    background-color: #ccd1d9;
    color: #ffffff;
}

/* 4. Поля ввода (Инпуты) */
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #ccd1d9;
    border-radius: 8px;
    padding: 8px 12px; /* Стандартный отступ */
    min-height: 35px;
    font-size: 14px;
}

/* Специальный стиль для поля пароля, чтобы освободить место справа */
/* В файле стилей, чтобы иконка не закрывала текст */
QLineEdit#passwordField {
    padding-right: 35px !important;
    background-color: white;
}



/* 5. Таблицы (для списков пользователей/тестов) */
QTableWidget {
    background-color: white;
    border: 1px solid #dee2e6;
    gridline-color: #f1f3f5;
    border-radius: 8px;
    selection-background-color: #e8f5e9;
    selection-color: #2e7d32;
}

QHeaderView::section {
    background-color: #f8f9fa;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #4CAF50;
    font-weight: bold;
}

/* 6. Вкладки (Tabs) */
QTabWidget::pane {
    border: 1px solid #dee2e6;
    background-color: white;
    border-radius: 5px;
}

QTabBar::tab {
    background-color: #e9ecef;
    padding: 12px 25px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: white;
    border-bottom: 3px solid #4CAF50;
    font-weight: bold;
}

/* 7. Статус ошибки (красный текст) */
QLabel#status_error {
    color: #d32f2f;
    font-size: 13px;
    font-weight: bold;
}


/* Добавь это в STYLESHEET в файле src/gui/styles/__init__.py */

QPushButton#secondary_button {
    background-color: transparent;
    color: #2e7d32;
    border: none;
    font-size: 14px;
    font-weight: bold;
    min-width: 0px;
    padding: 0px;
}

QPushButton#secondary_button:hover {
    color: #1b5e20;
    text-decoration: underline;
}

# Добавьте в конец STYLESHEET:

/* ===== КНОПКА РЕГИСТРАЦИИ ===== */
QPushButton#registerButton {
    background-color: #2196F3;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 10px 20px;
    font-weight: bold;
}

QPushButton#registerButton:hover {
    background-color: #1976D2;
}

/* ===== КНОПКА ОТМЕНЫ ===== */
QPushButton#cancelButton {
    background-color: #f44336;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 10px 20px;
    font-weight: bold;
}

QPushButton#cancelButton:hover {
    background-color: #d32f2f;
}



"""