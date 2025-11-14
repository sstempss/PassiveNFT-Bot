#!/usr/bin/env python3
"""
Скрипт запуска PassiveNFT Bot
"""
import os
import sys
import logging
from pathlib import Path

# Добавляем текущую папку в Python path
sys.path.append(str(Path(__file__).parent))

from bot import main

if __name__ == "__main__":
    print("🤖 Запуск PassiveNFT Bot...")
    print("📋 Проверка конфигурации...")
    
    # Проверяем наличие обязательных конфигураций
    try:
        from config import Config
        
        if Config.BOT_TOKEN == "8530441136:AAHto3A4Zqa5FnGG01cxL6SvU3jW8_Ai0iI":
            print("⚠️  ВНИМАНИЕ: Используется тестовый BOT_TOKEN!")
            print("   Обязательно замените на реальный токен в config.py")
        
        if Config.TON_WALLET_ADDRESS == "UQAij8pQ3HhdBn3lw6n9Iy2toOH9OMcBuL8yoSXTNpLJdfZJ":
            print("⚠️  ВНИМАНИЕ: Используется тестовый TON_WALLET_ADDRESS!")
            print("   Обязательно замените на реальный адрес кошелька в config.py")
            
        print("✅ Конфигурация загружена")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        sys.exit(1)
    
    try:
        # Запускаем бота
        main()
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)