#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Запуск всех тестов проекта
"""

import os
import subprocess
import sys

# Устанавливаем кодировку UTF-8
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Путь к Python из виртуального окружения
VENV_PYTHON = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.venv', 'Scripts', 'python.exe')


def run_command(command, description):
    """Выполнение команды"""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}\n")

    try:
        # Запускаем без shell=True для корректной обработки прерываний
        result = subprocess.run(
            command,
            shell=False,
            timeout=120  # Таймаут 120 секунд
        )

        # Exit code 5 = no tests collected (not a failure)
        if result.returncode == 5:
            print("⚠️ Тесты не найдены (пропущено)")
            return True

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        print("❌ Превышено время выполнения теста (120 сек)")
        return False
    except KeyboardInterrupt:
        print("\n⚠️ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        return False


def main():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("🏫 School Psychology Testing App")
    print("🧪 ЗАПУСК ТЕСТИРОВАНИЯ")
    print("="*60 + "\n")

    # Разбиваем команды на список аргументов
    tests = [
        ([VENV_PYTHON, "-m", "pytest", "tests/test_config.py", "-v"], "Тесты конфигурации"),
        ([VENV_PYTHON, "-m", "pytest", "tests/test_database.py", "-v"], "Тесты базы данных"),
        ([VENV_PYTHON, "-m", "pytest", "tests/test_auth.py", "-v"], "Тесты аутентификации"),
        ([VENV_PYTHON, "-m", "pytest", "tests/test_models.py", "-v"], "Тесты моделей"),
        ([VENV_PYTHON, "-m", "pytest", "tests/test_services.py", "-v"], "Тесты сервисов"),
    ]

    passed = 0
    failed = 0

    for command, description in tests:
        if run_command(command, description):
            passed += 1
            print(f"✅ {description} - ПРОЙДЕНО")
        else:
            failed += 1
            print(f"❌ {description} - ПРОВАЛЕНО")

    print("\n" + "="*60)
    print(f"📊 ИТОГИ: {passed} пройдено, {failed} провалено")
    print("="*60 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())