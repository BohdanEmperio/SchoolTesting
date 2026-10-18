#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты графического интерфейса
"""


import pytest


@pytest.mark.skip(reason="Требуется дисплей для GUI тестов")
class TestGUI:
    """Тесты интерфейса"""
    
    def test_import_pyside6(self):
        """Импорт PySide6"""
        from PySide6.QtWidgets import QApplication
        assert QApplication is not None
    
    def test_import_main_window(self):
        """Импорт главного окна"""
        from src.gui.main_window import MainWindow
        assert MainWindow is not None
    
    def test_import_auth_window(self):
        """Импорт окна авторизации"""
        from src.gui.auth_window import AuthWindow
        assert AuthWindow is not None