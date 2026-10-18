#!/usr/bin/env python3
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    print("✅ Пароль верный! Подключение успешно.")
    conn.close()
except Exception as e:
    print(f"❌ Ошибка: {e}")
    print("💡 Проверьте пароль в .env файле")