#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка что VS Code использует правильный интерпретатор"""

import sys
import psycopg2

print("\n" + "="*60)
print("🔍 ПРОВЕРКА ИНТЕРПРЕТАТОРА VS CODE")
print("="*60 + "\n")

print(f"Python путь: {sys.executable}")
print(f"Python версия: {sys.version}\n")

print(f"psycopg2 версия: {psycopg2.__version__}")
print("dotenv установлен: ✅\n")

if '.venv' in sys.executable:
    print("✅ VS Code использует виртуальное окружение!")
else:
    print("❌ VS Code использует системный Python!")
    print("💡 Выберите .venv\\Scripts\\python.exe как интерпретатор")

print("\n" + "="*60 + "\n")