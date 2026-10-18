#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка подключения к PostgreSQL"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*60)
print("🔍 ПРОВЕРКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ")
print("="*60 + "\n")

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        options=f'-c search_path={os.getenv("DB_SCHEMA", "psychology")}'
    )
    
    cursor = conn.cursor()
    
    # Проверка версии PostgreSQL
    cursor.execute("SELECT version();")
    pg_version = cursor.fetchone()[0]
    print(f"✅ PostgreSQL: {pg_version.split(',')[0]}\n")
    
    # Проверка схемы
    cursor.execute("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name = %s
    """, (os.getenv("DB_SCHEMA", "psychology"),))
    
    schema = cursor.fetchone()
    if schema:
        print(f"✅ Схема '{os.getenv('DB_SCHEMA')}' существует\n")
    else:
        print(f"❌ Схема '{os.getenv('DB_SCHEMA')}' не найдена\n")
    
    # Проверка таблиц
    cursor.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = %s
    """, (os.getenv("DB_SCHEMA", "psychology"),))
    
    table_count = cursor.fetchone()[0]
    print(f"✅ Таблиц в схеме: {table_count}\n")
    
    # Проверка пользователя
    cursor.execute("SELECT current_user;")
    current_user = cursor.fetchone()[0]
    print(f"✅ Подключён как: {current_user}\n")
    
    cursor.close()
    conn.close()
    
    print("="*60)
    print("🎉 ПОДКЛЮЧЕНИЕ УСПЕШНО!")
    print("="*60 + "\n")
    
except psycopg2.OperationalError as e:
    print(f"❌ Ошибка подключения: {e}\n")
    print("💡 Проверьте:")
    print("   1. PostgreSQL запущен")
    print("   2. Параметры в .env верны")
    print("   3. Пользователь существует")
    print("   4. БД создана\n")
    
except Exception as e:
    print(f"❌ Ошибка: {e}\n")