#!/usr/bin/env python3
"""
Professional Flask wrapper для PassiveNFT Bot
Оптимизировано для стабильного деплоя на TimeWeb
"""

import asyncio
import logging
import sys
import os
import signal
from flask import Flask, jsonify
from pathlib import Path

# Настройка логирования (безопасные пути)
log_dir = Path("/app/logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_dir / "bot.log")),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Создание Flask приложения
flask_app = Flask(__name__)

# Глобальные переменные для мониторинга
bot_running = False
bot_instance = None

@flask_app.route('/')
def home():
    """Главная страница - статус бота"""
    status = "running" if bot_running else "stopped"
    return jsonify({
        'status': status,
        'bot': 'PassiveNFT Bot',
        'version': '2.1.3 - Professional Deploy',
        'uptime': 'operational',
        'message': f'🤖 Telegram Bot {status} (Professional Version)'
    })

@flask_app.route('/health')
def health_check():
    """Проверка здоровья приложения"""
    return jsonify({
        'status': 'healthy' if bot_running else 'starting',
        'timestamp': __import__('datetime').datetime.now().isoformat(),
        'service': 'PassiveNFT Bot',
        'container': 'Docker'
    })

@flask_app.route('/status')
def status():
    """Детальный статус системы"""
    return jsonify({
        'service': 'PassiveNFT Bot',
        'version': '2.1.3 - Professional Deploy',
        'deployment': 'TimeWeb + Docker',
        'status': 'active' if bot_running else 'initializing',
        'features': [
            'Реферальная система',
            'TON Wallet подключение', 
            'Star подписки',
            'Приватные каналы',
            'Auto-start',
            '🔗 Dynamic Invite Links',
            '⏰ 24-hour Auto-refresh',
            '🛡️ One-time Protection',
            '🚀 Professional Deployment'
        ],
        'container': {
            'docker': True,
            'port': 8000,
            'health_check': 'enabled'
        }
    })

async def start_bot():
    """Безопасный запуск бота"""
    global bot_running, bot_instance
    
    try:
        logger.info("🤖 Инициализация Telegram бота...")
        
        # Импорт модуля бота
        sys.path.append('/app')
        
        # Попытка найти и запустить бота
        try:
            from bot_deploy_final_dynamic_links import PassiveNFTBot
            logger.info("✅ Модуль бота найден")
            
            # Создание экземпляра бота
            bot_instance = PassiveNFTBot()
            bot_running = True
            
            logger.info("🚀 Бот успешно запущен!")
            
            # Запуск polling в текущем event loop
            await bot_instance.run()
            
        except ImportError as e:
            logger.error(f"❌ Ошибка импорта бота: {e}")
            # Попробовать альтернативный способ
            try:
                from bot_deploy_final_dynamic_links import main
                await main()
                logger.info("✅ Альтернативный запуск выполнен")
            except Exception as alt_e:
                logger.error(f"❌ Альтернативный запуск также провалился: {alt_e}")
                raise
                
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска бота: {e}")
        logger.error(f"Traceback: {__import__('traceback').format_exc()}")
        bot_running = False
        raise

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info(f"📋 Получен сигнал {signum}, завершение работы...")
    sys.exit(0)

def run_bot_async():
    """Запуск бота в асинхронном режиме"""
    try:
        asyncio.run(start_bot())
    except Exception as e:
        logger.error(f"❌ Ошибка в асинхронном запуске: {e}")
        bot_running = False

if __name__ == "__main__":
    try:
        # Регистрация обработчиков сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("🔥 ЗАПУСК PassiveNFT Bot (Professional Version)")
        logger.info("📦 Платформа: TimeWeb + Docker")
        logger.info("🤖 Тип: Professional Telegram Bot")
        logger.info("🚀 Инициализация...")

        # Создание директорий
        os.makedirs('/app/logs', exist_ok=True)
        
        # Запуск бота в отдельном потоке
        import threading
        
        bot_thread = threading.Thread(
            target=run_bot_async, 
            daemon=True,
            name="TelegramBot"
        )
        bot_thread.start()
        
        logger.info("🌐 Запуск Flask веб-сервера на порту 8000...")
        
        # Запуск Flask сервера
        flask_app.run(
            host='0.0.0.0',
            port=8000,
            debug=False,
            use_reloader=False,
            threaded=True
        )
        
    except KeyboardInterrupt:
        logger.info("👋 Приложение остановлено пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.error(f"Traceback: {__import__('traceback').format_exc()}")
        sys.exit(1)
