#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генерация секретных ключей для .env"""

import secrets

from cryptography.fernet import Fernet

print("="*60)
print("🔑 ГЕНЕРАЦИЯ СЕКРЕТНЫХ КЛЮЧЕЙ")
print("="*60 + "\n")

# SECRET_KEY для JWT
secret_key = secrets.token_urlsafe(32)
print(f"SECRET_KEY={secret_key}\n")

# ENCRYPTION_KEY для шифрования данных
encryption_key = Fernet.generate_key().decode()
print(f"ENCRYPTION_KEY={encryption_key}\n")

print("="*60)
print("📋 Скопируйте эти значения в файл .env")
print("="*60)