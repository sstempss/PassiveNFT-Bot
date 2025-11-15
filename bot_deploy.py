#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PassiveNFT Bot - Render.com Deployment Version (Fixed)
С исправленным методом запуска для новых версий python-telegram-bot
"""
import asyncio
import logging
import sqlite3
import sys
import traceback
from pathlib import Path

# Импорты Telegram бота - ПЕРЕМЕЩЕНЫ В ГЛОБАЛЬНУЮ ОБЛАСТЬ
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class Database:
    """Простая SQLite база данных для хранения подписок"""
    
    def __init__(self, db_path: str = "passive_nft_bot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        user_id INTEGER PRIMARY KEY,
                        subscription_type TEXT NOT NULL,
                        start_date TEXT NOT NULL,
                        active INTEGER DEFAULT 1
                    )
                ''')
                conn.commit()
                logger.info("База данных инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise

class SafeConfig:
    """Безопасная конфигурация бота с fallback значениями"""
    
    def __init__(self):
        # Основные настройки
        self.BOT_TOKEN = self._get_env_var('BOT_TOKEN', '8530441136:AAHto3A4Zqa5FnGG01cxL6SvU3jW8_Ai0iI')
        self.ADMIN_USER_IDS = [8387394503]  # pro.player.egor
        
        # Настройки TON кошелька
        self.TON_WALLET_ADDRESS = self._get_env_var('TON_WALLET_ADDRESS', 'UQAij8pQ3HhdBn3lw6n9Iy2toOH9OMcBuL8yoSXTNpLJdfZJ')
        self.MANAGER_USERNAME = self._get_env_var('MANAGER_USERNAME', 'num6er9')
        self.BOT_USERNAME = self._get_env_var('BOT_USERNAME', 'PassiveNFT')
        
        # Настройки подписок
        self.SUBSCRIPTION_PLANS = [
            {
                "name": "на 150 человек",
                "price_ton": 150,
                "description": "Подписка на максимальное количество пользователей (150)"
            },
            {
                "name": "на 100 человек", 
                "price_ton": 100,
                "description": "Подписка на стандартное количество пользователей (100)"
            },
            {
                "name": "на 50 человек",
                "price_ton": 50,
                "description": "Подписка на базовое количество пользователей (50)"
            }
        ]
        
        # Тексты бота
        self.WELCOME_MESSAGE = """🤖 Добро пожаловать в PassiveNFT Bot!

💰 Этот бот позволяет получать пассивный доход от NFT коллекций

🚀 Для начала работы выберите подписку:

"""

        self.SUBSCRIPTION_SELECTED_MESSAGE = """✅ Подписка "{plan_name}" выбрана

💰 Стоимость: {price} TON
📝 Описание: {description}

Для завершения покупки:
1. Отправьте {price} TON на адрес:{wallet_address}


2. После оплаты нажмите кнопку "✅ Оплатил"
3. Подписка будет активирована автоматически

⚠️ Обязательно укажите в комментарии к платежу: {user_id}

💬 Если есть вопросы - обращайтесь к менеджеру: @{manager_username}"""

        self.PAYMENT_CONFIRMED_MESSAGE = """🎉 Оплата подтверждена!

Ваша подписка "{plan_name}" успешно активирована на {duration}!

📊 Статистика:
👥 Лимит пользователей: {limit}
💰 Стоимость подписки: {price} TON
📅 Дата активации: {date}

💡 Бот будет автоматически приносить пассивный доход от NFT"""

        self.ALREADY_SUBSCRIBED_MESSAGE = """⚠️ У вас уже есть активная подписка!

📊 Ваша текущая подписка:
🏷️ Тип: "{current_plan}"
📅 Активна до: {expiry_date}

💡 Для продления обратитесь к менеджеру: @{manager_username}"""

        self.ADMIN_MESSAGE = """🔧 Админ панель PassiveNFT Bot

👥 Пользователей с подписками: {subscribers_count}
💰 Общий доход: {total_revenue} TON

📋 Последние подписки:"""

        
    def _get_env_var(self, var_name: str, default_value: str = None) -> str:
        """Безопасное получение переменной окружения"""
        import os
        value = os.getenv(var_name, default_value)
        if not value:
            logger.warning(f"Переменная {var_name} не установлена, использую значение по умолчанию")
        return value
    
    def get_admin_usernames(self):
        """Получение списка админов по username (для отладки)"""
        return ["pro.player.egor", "admin"]  # Добавляем возможные admin username'ы

# Инициализация конфигурации
try:
    config = SafeConfig()
    logger.info("✅ Безопасная конфигурация загружена")
    logger.info(f"🤖 Бот: @{config.BOT_USERNAME}")
    logger.info(f"💰 Кошелек: {config.TON_WALLET_ADDRESS[:10]}...{config.TON_WALLET_ADDRESS[-10:]}")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки конфигурации: {e}")
    config = SafeConfig()  # Fallback на стандартные значения


class PassiveNFTBot:
    """Главный класс бота с исправленным методом запуска"""
    
    def __init__(self):
        self.config = config
        self.database = Database()
        self.application = None
        self.setup_telegram_application()
    
    def setup_telegram_application(self):
        """Настройка Telegram приложения"""
        try:
            
            # Создание приложения
            self.application = (
                Application.builder()
                .token(self.config.BOT_TOKEN)
                .build()
            )
            
            # Регистрация обработчиков
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("admin", self.admin_command))
            self.application.add_handler(CallbackQueryHandler(self.subscription_callback, pattern="^subscription_"))
            self.application.add_handler(CallbackQueryHandler(self.payment_callback, pattern="^payment_"))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
            logger.info("Telegram приложение настроено")
            
        except ImportError as e:
            logger.error(f"Ошибка импорта telegram библиотек: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка настройки приложения: {e}")
            raise
    
    async def clear_webhook_on_startup(self):
        """Очистка webhook перед запуском для решения конфликтов"""
        try:
            logger.info("🧹 Очистка старых webhook'ов...")
            await self.application.bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook очищен успешно")
            await asyncio.sleep(2)  # Даем время Telegram API обновиться
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при очистке webhook: {e}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        # Проверяем, есть ли у пользователя активная подписка
        subscription = self.get_user_subscription(user.id)
        if subscription:
            await update.message.reply_text(
                self.config.ALREADY_SUBSCRIBED_MESSAGE.format(
                    current_plan=subscription[1],
                    expiry_date="безлимит",  # Можно добавить логику вычисления даты
                    manager_username=self.config.MANAGER_USERNAME
                ),
                parse_mode='Markdown'
            )
            return
        
        # Отправляем приветственное сообщение с выбором подписки
        message = self.config.WELCOME_MESSAGE
        keyboard = []
        
        for i, plan in enumerate(self.config.SUBSCRIPTION_PLANS):
            button_text = f"{plan['name']} - {plan['price_ton']} TON"
            callback_data = f"subscription_{i}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """🤖 PassiveNFT Bot - Справка

💰 Этот бот предоставляет доступ к пассивному доходу от NFT коллекций

📋 Команды:
/start - Начать работу с ботом
/help - Показать эту справку
/admin - Админ панель (только для админов)

💬 Для вопросов: @{manager_username}

💡 Выберите подписку и начните зарабатывать уже сегодня!"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /admin"""
        user = update.effective_user
        
        # Проверяем, является ли пользователь админом
        if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
            await update.message.reply_text("❌ У вас нет доступа к админ панели")
            return
        
        # Получаем статистику
        stats = self.get_admin_stats()
        
        admin_text = self.config.ADMIN_MESSAGE.format(
            subscribers_count=stats['subscribers_count'],
            total_revenue=stats['total_revenue']
        )
        
        await update.message.reply_text(admin_text, parse_mode='Markdown')
    
    async def subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора подписки"""
        query = update.callback_query
        await query.answer()
        
        plan_index = int(query.data.split('_')[1])
        plan = self.config.SUBSCRIPTION_PLANS[plan_index]
        
        user = query.from_user
        
        message = self.config.SUBSCRIPTION_SELECTED_MESSAGE.format(
            plan_name=plan['name'],
            price=plan['price_ton'],
            description=plan['description'],
            wallet_address=self.config.TON_WALLET_ADDRESS,
            user_id=user.id,
            manager_username=self.config.MANAGER_USERNAME
        )
        
        # Кнопка подтверждения оплаты
        keyboard = [
            [InlineKeyboardButton("✅ Оплатил", callback_data=f"payment_{plan_index}_{user.id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик подтверждения оплаты"""
        query = update.callback_query
        await query.answer()
        
        parts = query.data.split('_')
        plan_index = int(parts[1])
        user_id = int(parts[2])
        
        plan = self.config.SUBSCRIPTION_PLANS[plan_index]
        
        # Активируем подписку
        self.activate_subscription(user_id, plan['name'])
        
        # Отправляем подтверждение
        from datetime import datetime
        confirmation_text = self.config.PAYMENT_CONFIRMED_MESSAGE.format(
            plan_name=plan['name'],
            duration="безлимит",
            limit=plan['name'].split()[2],  # Извлекаем число из названия
            price=plan['price_ton'],
            date=datetime.now().strftime("%d.%m.%Y %H:%M")
        )
        
        await query.message.edit_text(confirmation_text, parse_mode='Markdown')
        
        # Уведомляем админов
        await self.notify_admins(user_id, plan['name'], plan['price_ton'])
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        message = update.message.text.lower()
        
        if "help" in message or "помощь" in message:
            await self.help_command(update, context)
        elif "admin" in message and update.effective_user.id in self.config.ADMIN_USER_IDS:
            await self.admin_command(update, context)
        else:
            await update.message.reply_text(
                "🤖 Используйте /start для начала работы или /help для справки",
                parse_mode='Markdown'
            )
    
    def get_user_subscription(self, user_id: int):
        """Получение подписки пользователя"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM subscriptions WHERE user_id = ? AND active = 1",
                    (user_id,)
                )
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Ошибка получения подписки: {e}")
            return None
    
    def activate_subscription(self, user_id: int, plan_name: str):
        """Активация подписки пользователя"""
        try:
            from datetime import datetime
            
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO subscriptions (user_id, subscription_type, start_date, active) VALUES (?, ?, ?, ?)",
                    (user_id, plan_name, datetime.now().isoformat(), 1)
                )
                conn.commit()
                logger.info(f"Подписка активирована для пользователя {user_id}: {plan_name}")
        except Exception as e:
            logger.error(f"Ошибка активации подписки: {e}")
    
    def get_admin_stats(self):
        """Получение статистики для админов"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Количество подписчиков
                cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE active = 1")
                subscribers_count = cursor.fetchone()[0]
                
                # Примерный доход (сумма всех подписок)
                cursor.execute("SELECT subscription_type FROM subscriptions WHERE active = 1")
                plans = cursor.fetchall()
                
                total_revenue = 0
                for plan in plans:
                    for plan_config in self.config.SUBSCRIPTION_PLANS:
                        if plan[0] == plan_config['name']:
                            total_revenue += plan_config['price_ton']
                            break
                
                return {
                    'subscribers_count': subscribers_count,
                    'total_revenue': total_revenue
                }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {'subscribers_count': 0, 'total_revenue': 0}
    
    async def notify_admins(self, user_id: int, plan_name: str, amount: int):
        """Уведомление админов о новой подписке"""
        try:
            for admin_id in self.config.ADMIN_USER_IDS:
                try:
                    await self.application.bot.send_message(
                        chat_id=admin_id,
                        text=f"🎉 Новая подписка!\n\n👤 Пользователь: {user_id}\n📦 План: {plan_name}\n💰 Сумма: {amount} TON"
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить админа {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка уведомления админов: {e}")
    
    async def run(self):
        """Запуск бота с исправленным методом - ИСПРАВЛЕНО"""
        logger.info("🚀 Запуск PassiveNFT Bot на Render...")
        logger.info(f"🤖 Бот: @{self.config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...{self.config.TON_WALLET_ADDRESS[-10:]}")
        
        # Очистка webhook перед запуском
        await self.clear_webhook_on_startup()
        
        # Инициализация и запуск приложения
        await self.application.initialize()
        await self.application.start()
        
        try:
            # Запуск polling с современным подходом
            await self.application.updater.start_polling()
            logger.info("✅ Бот запущен и ожидает команды...")
            
            # Вместо устаревшего .idle() используем Event.wait()
            # Это позволяет боту работать бесконечно до остановки
            await asyncio.Event().wait()
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            # Корректная остановка бота
            try:
                if self.application.updater.running:
                    self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                logger.info("✅ Бот корректно остановлен")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при остановке: {e}")


async def main():
    """Главная функция запуска"""
    try:
        bot = PassiveNFTBot()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал остановки")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        sys.exit(1)
