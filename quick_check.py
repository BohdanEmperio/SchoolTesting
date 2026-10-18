#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Быстрая проверка без subprocess"""

import sys

print("\n" + "="*60)
print("🔍 БЫСТРАЯ ПРОВЕРКА ПАКЕТОВ")
print("="*60 + "\n")

print(f"Python: {sys.version.split()[0]}\n")

# Проверка через import (быстро, без subprocess)
packages = [
    ("PySide6", "PySide6"),
    ("psycopg2", "psycopg2-binary"),
    ("sqlalchemy", "SQLAlchemy"),
    ("alembic", "alembic"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("passlib", "passlib"),
    ("jose", "python-jose"),
    ("jwt", "PyJWT"),
    ("cryptography", "cryptography"),
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("openpyxl", "openpyxl"),
    ("docx", "python-docx"),
    ("jinja2", "jinja2"),
    ("lxml", "lxml"),
    ("dotenv", "dotenv"),
    ("pydantic", "pydantic"),
    ("pydantic_settings", "pydantic_settings"),
]

ok = 0
fail = 0

for import_name, pip_name in packages:
    try:
        __import__(import_name)
        print(f"✅ {import_name}")
        ok += 1
    except ImportError:
        print(f"❌ {import_name}")
        fail += 1

print("\n" + "="*60)
print(f"✅ Установлено: {ok}/{len(packages)}")
print(f"❌ Отсутствует: {fail}/{len(packages)}")
print("="*60 + "\n")