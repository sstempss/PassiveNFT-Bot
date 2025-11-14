#!/usr/bin/env python3
"""
Главный скрипт управления PassiveNFT Bot
"""
import sys
import os
import subprocess
import argparse
import sqlite3
from pathlib import Path

def check_dependencies():
    """Проверка зависимостей"""
    print("🔍 Проверка зависимостей...")
    
    required_packages = ['telegram']
    missing_packages = []
    
    try:
        import telegram
        print("✅ python-telegram-bot установлен")
    except ImportError:
        missing_packages.append('python-telegram-bot')
    
    if missing_packages:
        print(f"❌ Отсутствуют пакеты: {', '.join(missing_packages)}")
        print("Установите их командой: pip install -r requirements.txt")
        return False
    
    return True

def setup_bot():
    """Первоначальная настройка бота"""
    print("⚙️  Первоначальная настройка бота...")
    
    # Проверяем конфигурацию
    try:
        from config import Config
        
        changes_made = False
        
        # Проверяем BOT_TOKEN
        if Config.BOT_TOKEN == "8530441136:AAHto3A4Zqa5FnGG01cxL6SvU3jW8_Ai0iI":
            print("⚠️  ВНИМАНИЕ: Используется тестовый BOT_TOKEN!")
            print("   Замените на реальный токен в config.py")
            changes_made = True
        
        # Проверяем TON_WALLET_ADDRESS
        if Config.TON_WALLET_ADDRESS == "UQAij8pQ3HhdBn3lw6n9Iy2toOH9OMcBuL8yoSXTNpLJdfZJ":
            print("⚠️  ВНИМАНИЕ: Используется тестовый TON_WALLET_ADDRESS!")
            print("   Замените на реальный адрес кошелька в config.py")
            changes_made = True
        
        if changes_made:
            print("\n📝 Не забудьте обновить конфигурацию в config.py перед запуском!")
            return False
        else:
            print("✅ Конфигурация проверена")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        return False

def run_bot():
    """Запуск бота"""
    print("🤖 Запуск PassiveNFT Bot...")
    
    if not check_dependencies():
        return False
    
    if not setup_bot():
        return False
    
    try:
        # Запускаем бота
        subprocess.run([sys.executable, "bot.py"], check=True)
        return True
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска бота: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def run_tests():
    """Запуск тестов"""
    print("🧪 Запуск тестов...")
    
    try:
        result = subprocess.run([sys.executable, "test_bot.py"], 
                              capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Ошибка запуска тестов: {e}")
        return False

def run_admin_tools():
    """Запуск админских утилит"""
    print("🛠️  Запуск админских утилит...")
    
    try:
        subprocess.run([sys.executable, "admin_utils.py"], check=True)
        return True
    except Exception as e:
        print(f"❌ Ошибка запуска утилит: {e}")
        return False

def show_status():
    """Показать статус бота и БД"""
    print("📊 Статус PassiveNFT Bot")
    
    try:
        from database import DatabaseManager
        db = DatabaseManager()
        
        # Простая проверка БД
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        # Подсчет пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        # Подсчет подписок
        cursor.execute("SELECT COUNT(*) FROM subscriptions")
        sub_count = cursor.fetchone()[0]
        
        # Подсчет оплаченных подписок
        cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE payment_status = 'paid'")
        paid_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"👥 Пользователей: {user_count}")
        print(f"📋 Подписок: {sub_count}")
        print(f"💰 Оплачено: {paid_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка получения статуса: {e}")
        return False

def install_dependencies():
    """Установка зависимостей"""
    print("📦 Установка зависимостей...")
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True)
        print("✅ Зависимости установлены")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки зависимостей: {e}")
        return False

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description="PassiveNFT Bot Manager")
    parser.add_argument("command", choices=["start", "test", "admin", "status", "install"], 
                       help="Команда для выполнения")
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    
    args = parser.parse_args()
    
    print("🤖 PassiveNFT Bot Manager")
    print("=" * 40)
    
    if args.command == "start":
        run_bot()
    elif args.command == "test":
        run_tests()
    elif args.command == "admin":
        run_admin_tools()
    elif args.command == "status":
        show_status()
    elif args.command == "install":
        install_dependencies()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Интерактивный режим
        print("🤖 PassiveNFT Bot Manager")
        print("=" * 40)
        print("Выберите действие:")
        print("1. 🚀 Запустить бота")
        print("2. 🧪 Запустить тесты")
        print("3. 🛠️  Админские утилиты")
        print("4. 📊 Показать статус")
        print("5. 📦 Установить зависимости")
        print("0. ❌ Выход")
        
        while True:
            choice = input("\nВаш выбор: ").strip()
            
            if choice == "0":
                break
            elif choice == "1":
                run_bot()
            elif choice == "2":
                run_tests()
            elif choice == "3":
                run_admin_tools()
            elif choice == "4":
                show_status()
            elif choice == "5":
                install_dependencies()
            else:
                print("❌ Неверный выбор")
    else:
        # Режим командной строки
        main()