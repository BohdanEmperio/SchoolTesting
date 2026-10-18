#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка установки библиотек - Версия 3 (БЕЗ КОНФЛИКТОВ)
"""

import subprocess
import sys

print("\n" + "="*70)
print("🔍 ПРОВЕРКА УСТАНОВЛЕННЫХ БИБЛИОТЕК")
print("="*70 + "\n")

print(f"Python версия: {sys.version}\n")

# Список пакетов для проверки (имя pip)
PACKAGES = [
    "PySide6",
    "PySide6-Addons",
    "psycopg2-binary",
    "SQLAlchemy",
    "alembic",
    "fastapi",
    "uvicorn",
    "passlib",
    "python-jose",
    "PyJWT",
    "cryptography",
    "pandas",
    "numpy",
    "openpyxl",
    "python-docx",
    "Jinja2",
    "lxml",
    "python-dotenv",
    "pydantic",
    "pydantic-settings",
]

installed = 0
missing = 0

for package in PACKAGES:
    try:
        # Проверка через pip (без импорта!)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # Извлекаем версию
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    version = line.split(':')[1].strip()
                    print(f"✅ {package:<30} {version}")
                    installed += 1
                    break
        else:
            print(f"❌ {package:<30} НЕ УСТАНОВЛЕНО")
            missing += 1
            
    except Exception as e:
        print(f"❌ {package:<30} Ошибка: {e}")
        missing += 1

print("\n" + "="*70)
print(f"✅ Установлено: {installed}/{len(PACKAGES)}")
print(f"❌ Отсутствует: {missing}/{len(PACKAGES)}")
print("="*70 + "\n")

if missing == 0:
    print("🎉 ВСЕ БИБЛИОТЕКИ УСТАНОВЛЕНЫ!\n")
    sys.exit(0)
else:
    print("⚠️ Установите отсутствующие:\n")
    print("   pip install -r requirements.txt\n")
    sys.exit(1)