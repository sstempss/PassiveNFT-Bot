#!/usr/bin/env python3
"""
Flask wrapper для запуска Telegram бота на TimeWeb
Создано для совместимости с панелью управления TimeWeb
"""

import asyncio
import logging
import sys
import os
from flask import Flask, jsonify

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/user/project/logs/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Создание Flask приложения для совместимости с TimeWeb
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    """Главная страница - индикатор работы бота"""
    return jsonify({
        'status': 'active',
        'bot': 'PassiveNFT Bot',
        'version': '2.1.2 - Dynamic Invite Links',
        'uptime': 'running',
        'message': '🤖 Telegram Bot с динамическими ссылками работает корректно'
    })

@flask_app.route('/health')
def health_check():
    """Проверка здоровья бота"""
    return jsonify({
        'status': 'healthy',
        'timestamp': __import__('datetime').datetime.now().isoformat(),
        'service': 'PassiveNFT Bot'
    })

@flask_app.route('/status')
def status():
    """Детальный статус бота"""
    return jsonify({
        'service': 'PassiveNFT Bot',
        'version': '2.1.2 - Dynamic Invite Links',
        'deployment': 'TimeWeb',
        'status': 'active',
        'features': [
            'Реферальная система',
            'TON Wallet подключение', 
            'Star подписки',
            'Приватные каналы',
            'Auto-start',
            '🔗 Dynamic Invite Links',
            '⏰ 24-hour Auto-refresh',
            '🛡️ One-time Protection'
        ]
    })

def run_telegram_bot():
    """Запуск Telegram бота в фоновом режиме"""
    try:
        # Импорт основного модуля бота с динамическими ссылками
        from bot_deploy_final_dynamic_links import main
        
        logger.info("🚀 Запуск Telegram бота с динамическими ссылками...")
        
        # Запуск бота
        asyncio.run(main())
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        logger.error(f"Traceback: {__import__('traceback').format_exc()}")

if __name__ == "__main__":
    try:
        logger.info("🔥 ЗАПУСК PassiveNFT Bot (Dynamic Invite Links Version)")
        logger.info("📦 Платформа: TimeWeb hosting")
        logger.info("🤖 Тип: Telegram Bot + Flask wrapper")
        logger.info("🔗 Функция: Dynamic Invite Links")
        logger.info("🚀 Инициализация...")

        # Создание директории для логов
        os.makedirs('/home/user/project/logs', exist_ok=True)
        
        # Запуск Flask сервера на порту 8000
        # Flask запускается в отдельном потоке, основной процесс - бот
        import threading
        from werkzeug.serving import make_server
        
        # Запуск бота в фоновом потоке
        bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        bot_thread.start()
        
        logger.info("🌐 Запуск Flask веб-сервера на порту 8000...")
        
        # Создание и запуск HTTP сервера
        server = make_server('0.0.0.0', 8000, flask_app, threaded=True)
        
        # Главный цикл - сервер работает постоянно
        server.serve_forever()
        
    except KeyboardInterrupt:
        logger.info("👋 Приложение остановлено пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.error(f"Traceback: {__import__('traceback').format_exc()}")
        sys.exit(1)
