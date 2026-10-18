#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Панель психолога
"""

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from src.gui.styles.live_reload import load_stylesheet


class PsychologistDashboard(QWidget):
    """Панель психолога"""
    
    def __init__(self, auth_service, db_service, user_data, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.db_service = db_service
        self.user_data = user_data
        
        self.setStyleSheet(load_stylesheet())
        self.setup_ui()
    
    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout()
        
        header = QLabel("👨‍⚕️ Панель Психолога")
        header.setObjectName("title")
        layout.addWidget(header)
        
        tabs = QTabWidget()
        tabs.addTab(QWidget(), "📊 Результаты")
        tabs.addTab(QWidget(), "👥 Ученики")
        tabs.addTab(QWidget(), "📝 Тесты")
        tabs.addTab(QWidget(), "📈 Отчёты")
        
        layout.addWidget(tabs)
        self.setLayout(layout)