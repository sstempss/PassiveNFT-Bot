#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PassiveNFT Bot - ВЕРСИЯ С ИСПРАВЛЕННОЙ РЕГИСТРАЦИЕЙ ПОЛЬЗОВАТЕЛЕЙ
"""
import asyncio
import logging
import sqlite3
import sys
import traceback
from pathlib import Path
from datetime import datetime

# Импорты Telegram бота - ГЛОБАЛЬНЫЕ ИМПОРТЫ
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

# ИМПОРТЫ ДЛЯ ВЕБ-СЕРВЕРА (для решения проблемы с портом на Render.com)
import os
import aiohttp
from aiohttp import web

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
    """База данных с поддержкой регистрации пользователей"""
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
                # Создаем таблицу для реферальной системы
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS referrals (
                        referrer_id INTEGER PRIMARY KEY,
                        referral_code TEXT UNIQUE NOT NULL,
                        total_referrals INTEGER DEFAULT 0,
                        total_earnings REAL DEFAULT 0.0
                    )
                ''')
                # Создаем таблицу для временного хранения информации о реферерах
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pending_referrals (
                        user_id INTEGER PRIMARY KEY,
                        referrer_id INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES subscriptions (user_id)
                    )
                ''')
                # Создаем таблицу пользователей для регистрации
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        registration_date TEXT,
                        referral_code TEXT UNIQUE
                    )
                ''')
                conn.commit()
            logger.info("База данных инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    def get_or_create_user(self, user_id: int, username: str, first_name: str, last_name: str) -> str:
        """Получить или создать пользователя"""
        try:
            # Сначала попробуем получить существующего пользователя
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                
                if result:
                    referral_code = result[0]
                    logger.info(f"✅ Пользователь {user_id} уже существует в базе с кодом {referral_code}")
                else:
                    # Создаем нового пользователя
                    referral_code = self.generate_referral_code()
                    
                    cursor.execute("""
                        INSERT INTO users (user_id, username, first_name, last_name, registration_date, referral_code)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (user_id, username, first_name, last_name, datetime.now().isoformat(), referral_code))
                    conn.commit()
                    logger.info(f"✅ Создан новый пользователь: {user_id} с кодом {referral_code}")
                
                return referral_code
        except Exception as e:
            logger.error(f"❌ Ошибка при регистрации пользователя {user_id}: {e}")
            # В случае ошибки возвращаем сгенерированный код
            return self.generate_referral_code()
    
    def generate_referral_code(self) -> str:
        """Генерация уникального реферального кода"""
        import random
        import string
        
        try:
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM users WHERE referral_code = ?", (code,))
                    count = cursor.fetchone()[0]
                    
                    if count == 0:
                        return code
        except Exception as e:
            logger.error(f"Ошибка генерации реферального кода: {e}")
            # Возвращаем простой код в случае ошибки
            import time
            return f"REF{int(time.time())}"

class SafeConfig:
    """Безопасная конфигурация бота с активными подписками"""
    def __init__(self):
        # Основные настройки
        self.BOT_TOKEN = self._get_env_var('BOT_TOKEN', '8530441136:AAHto3A4Zqa5FnGG01cxL6SvU3jW8_Ai0iI')
        self.ADMIN_USER_IDS = [8387394503] # pro.player.egor

        # Настройки TON кошелька
        self.TON_WALLET_ADDRESS = self._get_env_var('TON_WALLET_ADDRESS', 'UQAij8pQ3HhdBn3lw6n9Iy2toOH9OMcBuL8yoSXTNpLJdfZJ')
        self.MANAGER_USERNAME = self._get_env_var('MANAGER_USERNAME', 'num6er9')
        self.BOT_USERNAME = self._get_env_var('BOT_USERNAME', 'PassiveNFT')
        
        # Настройки для активных подписок
        self.STARS_USERNAME = self._get_env_var('STARS_USERNAME', 'alvatas')

        # Настройки подписок - БЕЗ ЖИРНОГО ТЕКСТА
        self.SUBSCRIPTION_PLANS = [
            {
                "name": "на 150 человек",
                "description": """🖼️ 5 NFT в ДЕНЬ, 4 гифта в ДЕНЬ 🖼️
                
📅 150 NFT в МЕСЯЦ, 120 гифтов в МЕСЯЦ

📊 Процент победы одного участника составляет 0,67% на одно NFT, количество разыгрываемых NFT в день – 5, следственно 5*0,67% = 3,35% на победу за день, в месяц получается 100,5%

🎁 На гифты за звезды процент победы на одного участника составляет 0,67%, количество разыгрываемых гифтов в день – 4, следственно 4*0,67% = 2,68% на победу за день, в месяц получается 80,4%

💰 окуп от х1 до х5""",
                "price_ton": 4
            },
            {
                "name": "на 100 человек",
                "description": """🖼️ 6 NFT в день, 4 гифта в день 🖼️
                
📅 180 NFT в месяц, 120 гифтов в месяц

📊 Процент победы одного участника составляет 1% на одно NFT, количество разыгрываемых NFT в день – 6, следственно 6*1% = 6% на победу за день, в месяц получается 180%

🎁 На гифты за звезды процент победы на одного участника составляет 0,67%, количество разыгрываемых гифтов в день – 4, следственно 4*1% = 4% на победу за день, в месяц получается 120%

💵 Один человек минимально получает возврат средств в 50% от стоимости подписки в месяц (в размере 1 NFT+гифт за 50 зв.)

💰 окуп от х1 до х8""",
                "price_ton": 7
            },
            {
                "name": "на 50 человек",
                "description": """🖼️ 7 NFT в день, 4 гифта в день 🖼️
                
📅 210 NFT в месяц, 120 гифтов в месяц

📊 Процент победы одного участника составляет 1% на одно NFT, количество разыгрываемых NFT в день – 7, следственно 7*2% = 14% на победу за день, в месяц получается 420%

🎁 На гифты за звезды процент победы одного участника составляет 2%, количество разыгрываемых гифтов в день – 4, следственно 4*2% = 8% на победу за день, в месяц получается 240%

💰 На одного участника в ТГК получается возврат средств в 70% от стоимости подписки в месяц (в размере 4 NFT+ 2 гифта за 50 зв.)

💰 окуп от х1 до х2,5-3""",
                "price_ton": 11
            }
        ]

        # Настройки для активных подписок (звездочки)
        self.STAR_SUBSCRIPTION_PLANS = [
            {
                "name": "Вход 25 звездочек",
                "stars": 25,
                "ton_price": 1.2
            },
            {
                "name": "Вход 50 звездочек", 
                "stars": 50,
                "ton_price": 2.4
            },
            {
                "name": "Вход 75 звездочек",
                "stars": 75, 
                "ton_price": 3.6
            },
            {
                "name": "Вход 100 звездочек",
                "stars": 100,
                "ton_price": 4.8
            }
        ]

        # Приветственные сообщения - БЕЗ ЖИРНОГО ТЕКСТА
        self.WELCOME_MESSAGE = """🤖 Добро пожаловать в PassiveNFT Bot!

💰 Получайте пассивный доход от NFT проектов
👥 Присоединяйтесь к растущему сообществу
⭐ Пользуйтесь нашими услугами удобно и просто

Выберите действие:"""
        
        # Сообщение для реферального входа
        self.REFERRAL_WELCOME_MESSAGE = """🤖 Добро пожаловать в PassiveNFT Bot!

🎁 Вас пригласил друг!
💰 Получайте пассивный доход от NFT проектов
👥 Присоединяйтесь к растущему сообществу
⭐ Пользуйтесь нашими услугами удобно и просто

Выберите действие:"""

        # Описание подписок - БЕЗ ЖИРНОГО ТЕКСТА
        self.SUBSCRIPTION_DESCRIPTION = """💳 ПОДПИСКИ - БЕЗ ЖИРНОГО ТЕКСТА

Выберите тип подписки:"""

        # Получаем переменные окружения
    def _get_env_var(self, var_name: str, default_value: str = None) -> str:
        """Безопасное получение переменной окружения"""
        import os
        value = os.getenv(var_name, default_value)
        if not value:
            logger.warning(f"Переменная {var_name} не установлена, использую значение по умолчанию")
        return value

    def get_admin_usernames(self):
        """Получение списка админов по username"""
        return ["pro.player.egor", "admin"]

# Инициализация конфигурации
try:
    if os.path.exists('config_deploy.py'):
        from config_deploy import config
        logger.info("Конфигурация загружена из config_deploy.py")
    else:
        config = SafeConfig()
        logger.info("Используется стандартная конфигурация")
except Exception as e:
    logger.error(f"Ошибка загрузки конфигурации: {e}")
    config = SafeConfig()


class PassiveNFTBot:
    """Главный класс бота с активными подписками"""
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

            # Регистрация команд
            self.application.add_handler(CommandHandler("start", self.start_command))
            
            # Команды для подтверждения оплаты и рефералов
            self.application.add_handler(CommandHandler("confirm_payment", self.confirm_payment_command))
            
            # Админ команды
            self.application.add_handler(CommandHandler("adminserveraa", self.admin_command))
            self.application.add_handler(CommandHandler("adminserveraastat", self.admin_stats_command))
            self.application.add_handler(CommandHandler("adminserveraapeople", self.admin_people_command))
            self.application.add_handler(CommandHandler("adminserveraaref", self.admin_referrals_command))
            self.application.add_handler(CommandHandler("broadcast", self.broadcast_command))
            
            # Обработчики подписок
            self.application.add_handler(CallbackQueryHandler(self.subscription_callback, pattern="^subscription$"))
            self.application.add_handler(CallbackQueryHandler(self.select_stars_callback, pattern="^select_stars$"))
            self.application.add_handler(CallbackQueryHandler(self.select_ton_callback, pattern="^select_ton$"))
            self.application.add_handler(CallbackQueryHandler(self.subscription_plan_callback, pattern="^subscription_plan_"))
            self.application.add_handler(CallbackQueryHandler(self.ton_subscription_plan_callback, pattern="^ton_subscription_plan_"))
            self.application.add_handler(CallbackQueryHandler(self.payment_callback, pattern="^payment_"))
            
            # Новые обработчики для активных подписок
            self.application.add_handler(CallbackQueryHandler(self.activity_subscription_callback, pattern="^activity_subscription_"))
            self.application.add_handler(CallbackQueryHandler(self.star_subscription_plan_callback, pattern="^star_plan_"))
            self.application.add_handler(CallbackQueryHandler(self.stars_payment_callback, pattern="^stars_payment_"))
            self.application.add_handler(CallbackQueryHandler(self.copy_stars_ton_callback, pattern="^copy_stars_ton_"))
            
            # Существующие обработчики
            self.application.add_handler(CallbackQueryHandler(self.contact_callback, pattern="^contact$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_callback, pattern="^referral$"))
            self.application.add_handler(CallbackQueryHandler(self.get_referral_link_callback, pattern="^get_referral$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_stats_callback, pattern="^referral_stats$"))
            self.application.add_handler(CallbackQueryHandler(self.copy_ton_callback, pattern="^copy_ton_"))
            self.application.add_handler(CallbackQueryHandler(self.back_callback, pattern="^back$"))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

            logger.info("Telegram приложение настроено")
        except Exception as e:
            logger.error(f"Ошибка настройки приложения: {e}")
            raise

    async def clear_webhook_on_startup(self):
        """Очистка webhook перед запуском для решения конфликтов"""
        try:
            logger.info("🧹 Очистка старных webhook'ов...")
            await self.application.bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook очищен успешно")
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при очистке webhook: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start с обработкой реферальных параметров"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: /start от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user
            args = context.args
            
            # Регистрируем пользователя в базе данных
            try:
                referral_code = self.database.get_or_create_user(
                    user_id=user.id,
                    username=user.username or "",
                    first_name=user.first_name or "",
                    last_name=user.last_name or ""
                )
                logger.info(f"✅ Пользователь {user.id} зарегистрирован в базе данных с кодом {referral_code}")
            except Exception as e:
                logger.error(f"❌ Ошибка регистрации пользователя {user.id}: {e}")
                # Продолжаем работу даже при ошибке регистрации
            
            # Проверяем, есть ли реферальный параметр
            referrer_id = None
            if args and len(args) > 0:
                arg = args[0]
                if arg.startswith('ref_'):
                    try:
                        referrer_id = int(arg[4:])  # Убираем "ref_" и получаем ID
                        if referrer_id != user.id:  # Нельзя быть реферером самому себе
                            # Сохраняем информацию о рефере временно
                            self.save_pending_referral(user.id, referrer_id)
                            logger.info(f"Пользователь {user.id} пришел от реферера {referrer_id}")
                    except ValueError:
                        pass  # Неверный формат, игнорируем

            # Выбираем соответствующее приветственное сообщение
            if referrer_id:
                welcome_text = self.config.REFERRAL_WELCOME_MESSAGE
            else:
                welcome_text = self.config.WELCOME_MESSAGE

            # ОРИГИНАЛЬНЫЕ КНОПКИ: Подписки, Связь, Реферальная система
            keyboard = [
                [InlineKeyboardButton("💳 Подписки", callback_data="subscription")],
                [InlineKeyboardButton("💬 Связь", callback_data="contact")],
                [InlineKeyboardButton("👥 Реферальная система", callback_data="referral")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
            logger.info(f"✅ /start выполнен успешно для пользователя {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в start_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def confirm_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды подтверждения оплаты и добавления реферала"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: /confirm_payment от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user
            
            # Проверяем, есть ли для этого пользователя ожидающий реферер
            pending_referrer = self.get_pending_referrer(user.id)
            if pending_referrer:
                # Добавляем реферала в базу
                success = self.add_referral(pending_referrer, user.id)
                if success:
                    # Удаляем запись об ожидающем реферере
                    self.remove_pending_referral(user.id)
                    await update.message.reply_text("✅ Оплата подтверждена! Реферал успешно добавлен.")
                else:
                    await update.message.reply_text("❌ Ошибка при добавлении реферала.")
            else:
                await update.message.reply_text("ℹ️ Для вас нет ожидающих рефереров.")
            
            logger.info(f"✅ /confirm_payment выполнен для пользователя {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в confirm_payment_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    def save_pending_referral(self, user_id: int, referrer_id: int):
        """Сохранение информации о временном рефере"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                from datetime import datetime
                cursor.execute(
                    "INSERT OR REPLACE INTO pending_referrals (user_id, referrer_id, created_at) VALUES (?, ?, ?)",
                    (user_id, referrer_id, datetime.now().isoformat())
                )
                conn.commit()
                logger.info(f"Сохранен временный реферер {referrer_id} для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка сохранения временного реферера: {e}")

    def get_pending_referrer(self, user_id: int):
        """Получение ожидающего реферера для пользователя"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT referrer_id FROM pending_referrals WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Ошибка получения ожидающего реферера: {e}")
            return None

    def remove_pending_referral(self, user_id: int):
        """Удаление записи об ожидающем рефере"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM pending_referrals WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()
                logger.info(f"Удален временный реферер для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка удаления временного реферера: {e}")

    def add_referral(self, referrer_id: int, referred_user_id: int):
        """Добавление реферала в базу данных"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Генерируем реферальный код для нового пользователя
                referral_code = self.database.generate_referral_code()
                
                # Добавляем реферала в таблицу referrals
                cursor.execute("""
                    INSERT OR REPLACE INTO referrals (referrer_id, referral_code, total_referrals, total_earnings)
                    VALUES (?, ?, 0, 0.0)
                """, (referrer_id, referral_code))
                
                # Увеличиваем счетчик рефералов у реферера
                cursor.execute("""
                    UPDATE referrals 
                    SET total_referrals = total_referrals + 1 
                    WHERE referrer_id = ?
                """, (referrer_id,))
                
                conn.commit()
                logger.info(f"Добавлен реферал: {referred_user_id} от {referrer_id}")
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления реферала: {e}")
            return False

    async def subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Подписки' - БЕЗ ЖИРНОГО ТЕКСТА"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: subscription callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # ОРИГИНАЛЬНОЕ общее описание подписок
            subscription_text = self.config.SUBSCRIPTION_DESCRIPTION

            # КНОПКИ ВЫБОРА ТИПА ПОДПИСКИ
            keyboard = [
                [InlineKeyboardButton("⚡ С активностями (за звездочки)", callback_data="select_stars")],
                [InlineKeyboardButton("💎 Без активностей (за TON)", callback_data="select_ton")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(subscription_text, reply_markup=reply_markup)
                logger.info(f"✅ Подписки открыты для пользователя {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Подписки уже открыты!")
                    logger.info(f"ℹ️ Подписки уже открыты для пользователя {update.effective_user.id}")
                else:
                    await query.answer("Ошибка при открытии подписок.")
                    logger.error(f"❌ Ошибка BadRequest в subscription_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в subscription_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def ton_subscription_plan_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора обычного плана TON (прямой переход к оплате)"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: ton_subscription_plan callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Извлекаем номер плана
            plan_index = int(query.data.split('_')[-1])
            plan = self.config.SUBSCRIPTION_PLANS[plan_index]

            # Формируем текст для прямого перехода к оплате
            plan_text = f"""💎 ПЛАН: {plan['name']}

{plan['description']}

💰 Цена: {plan['price_ton']} TON

Для оплаты перейдите к менеджеру: @{self.config.MANAGER_USERNAME}"""

            # Кнопка "Назад"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="select_ton")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(plan_text, reply_markup=reply_markup)
            logger.info(f"✅ План {plan['name']} показан пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в ton_subscription_plan_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def subscription_plan_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора конкретной подписки - выбор типа подписки"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: subscription_plan callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Извлекаем номер плана
            plan_index = int(query.data.split('_')[-1])
            plan = self.config.SUBSCRIPTION_PLANS[plan_index]

            # Кнопки выбора типа оплаты
            keyboard = [
                [InlineKeyboardButton(f"💳 Оплатить {plan['price_ton']} TON", callback_data=f"payment_{plan_index}")],
                [InlineKeyboardButton("💎 Оплатить криптовалютой", callback_data=f"ton_subscription_plan_{plan_index}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(plan['description'], reply_markup=reply_markup)
            logger.info(f"✅ План {plan['name']} показан пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в subscription_plan_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Оплатить' - БЕЗ ЖИРНОГО ТЕКСТА"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: payment callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Извлекаем номер плана
            plan_index = int(query.data.split('_')[-1])
            plan = self.config.SUBSCRIPTION_PLANS[plan_index]

            # Формируем сообщение об оплате с кликабельным TON адресом
            payment_text = f"""💰 ОПЛАТА: {plan['price_ton']} TON

Адрес кошелька:
<code>{self.config.TON_WALLET_ADDRESS}</code>

после оплаты обратитесь к менеджеру <a href="https://t.me/{self.config.MANAGER_USERNAME}">здесь</a> для подтверждения оплаты.

⚠️ ВАЖНО: Для копирования адреса кошелька нажмите на адрес выше."""

            # Кнопки оплаты
            keyboard = [
                [InlineKeyboardButton("🔗 Скопировать адрес", callback_data=f"copy_ton_{plan_index}")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"subscription_plan_{plan_index}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='HTML')
            logger.info(f"✅ Оплата {plan['name']} показана пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в payment_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def activity_subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора активных подписок"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: activity_subscription callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Кнопки выбора уровня звездочек
            keyboard = [
                [InlineKeyboardButton("⚡ С активностями (за звездочки)", callback_data="select_stars")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Выберите способ оплаты для активных подписок:", reply_markup=reply_markup)
            logger.info(f"✅ Активные подписки показаны пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в activity_subscription_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def select_stars_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора активных подписок (звездочки)"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: select_stars callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Показываем описание активностей
            activity_text = """⚡ АКТИВНЫЕ ПОДПИСКИ (ЗА ЗВЕЗДОЧКИ)

за вход в стоимость в звездочки вы получите шанс приумножить свою вложения вплоть до х20, всё зависит лишь от вашей скорости и удачи.

в подписку входят:

✅ доступ к закрытому ТГК где проходят активности
✅ различные активности КАЖДЫЙ час с 9:00 до 21:00 по МСК
✅ 13 активнотей в ДЕНЬ
✅ 390 активностей в МЕСЯЦ

выдачи происходят в течении 5-7 минут после завершения активности."""

            # Кнопки выбора уровня звездочек
            keyboard = [
                [InlineKeyboardButton("⭐️ ВХОД 25 ЗВЕЗДОЧЕК", callback_data="star_plan_25")],
                [InlineKeyboardButton("⭐️ ВХОД 50 ЗВЕЗДОЧЕК", callback_data="star_plan_50")],
                [InlineKeyboardButton("⭐️ ВХОД 75 ЗВЕЗДОЧЕК", callback_data="star_plan_75")],
                [InlineKeyboardButton("⭐️ ВХОД 100 ЗВЕЗДОЧЕК", callback_data="star_plan_100")],
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(activity_text, reply_markup=reply_markup)
            logger.info(f"✅ Активные подписки показаны пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в select_stars_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def select_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора обычных подписок (TON)"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: select_ton callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Показываем список обычных планов для TON
            plans_text = """💎 ОБЫЧНЫЕ ПОДПИСКИ (ЗА TON)

Выберите план:"""

            # Кнопки выбора планов
            keyboard = []
            for i, plan in enumerate(self.config.SUBSCRIPTION_PLANS):
                keyboard.append([InlineKeyboardButton(f"{plan['name']} - {plan['price_ton']} TON", callback_data=f"ton_subscription_plan_{i}")])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="subscription")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(plans_text, reply_markup=reply_markup)
            logger.info(f"✅ Обычные подписки показаны пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в select_ton_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def star_subscription_plan_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора конкретного плана звездочек"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: star_subscription_plan callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Извлекаем количество звездочек
            stars = int(query.data.split('_')[-1])

            # Находим соответствующий план звездочек
            star_plan = None
            for plan in self.config.STAR_SUBSCRIPTION_PLANS:
                if plan['stars'] == stars:
                    star_plan = plan
                    break

            if not star_plan:
                await query.answer("❌ Ошибка: план не найден")
                return

            # Формируем описание плана
            plan_text = f"""⭐️ ПЛАН: {star_plan['name']}

💰 Стоимость: ~{star_plan['ton_price']} TON (эквивалентно ~{stars} звездам)

Доступ ко всем активностям и закрытому ТГК"""

            # Кнопка "Оплатить"
            keyboard = [
                [InlineKeyboardButton(f"💳 Оплатить через звездочки", callback_data=f"stars_payment_{stars}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="select_stars")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(plan_text, reply_markup=reply_markup)
            logger.info(f"✅ План звездочек {stars} показан пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в star_subscription_plan_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def stars_payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик оплаты через звездочки"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: stars_payment callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Извлекаем количество звездочек
            parts = query.data.split('_')
            stars = int(parts[2])

            # Находим соответствующий план звездочек
            star_plan = None
            for plan in self.config.STAR_SUBSCRIPTION_PLANS:
                if plan['stars'] == stars:
                    star_plan = plan
                    break

            if not star_plan:
                await query.answer("❌ Ошибка: план не найден")
                return

            # Формируем сообщение об оплате с кликабельным TON адресом
            payment_text = f"""💰 ОПЛАТА: ~{star_plan['ton_price']} TON (эквивалентно ~{stars} звездам)

Адрес кошелька:
<code>{self.config.TON_WALLET_ADDRESS}</code>

для оплаты ЗВЕЗДОЧКАМИ перейдите <a href="https://t.me/{self.config.STARS_USERNAME}">сюда</a> и отправьте подарком стоимость подписки + оплата комиссии

после оплаты обратитесь к менеджеру <a href="https://t.me/{self.config.MANAGER_USERNAME}">здесь</a> для подтверждения оплаты и для получения ссылки в закрытый ТГК.

⚠️ ВАЖНО: Для копирования адреса кошелька нажмите на адрес выше."""

            # Кнопка "Назад к плану"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data=f"star_plan_{stars}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='HTML')
            logger.info(f"✅ Оплата через звездочки {stars} показана пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в stars_payment_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def copy_stars_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик копирования TON адреса для звездочек"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: copy_stars_ton callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Извлекаем количество звездочек
            parts = query.data.split('_')
            stars = int(parts[2])

            # Формируем сообщение с адресом кошелька
            address_message = f"""💰 Адрес для оплаты {stars} звездочек:

<code>{self.config.TON_WALLET_ADDRESS}</code>

⚠️ Скопируйте адрес выше и используйте его для оплаты!"""

            # Кнопка "Назад к оплате"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад к оплате", callback_data=f"stars_payment_{stars}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(address_message, reply_markup=reply_markup, parse_mode='HTML')
            logger.info(f"✅ Адрес кошелька для {stars} звездочек показан пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в copy_stars_ton_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def contact_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Связь' с ОРИГИНАЛЬНЫМ текстом"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: contact callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            contact_text = f"""💬 СВЯЗЬ

Менеджер: @{self.config.MANAGER_USERNAME}

💡 Для оплаты через звездочки: @{self.config.STARS_USERNAME}

📞 Если у вас возникли вопросы, обращайтесь!"""

            # ОРИГИНАЛЬНЫЕ КНОПКИ
            keyboard = [
                [InlineKeyboardButton("📞 Написать менеджеру", url=f"https://t.me/{self.config.MANAGER_USERNAME}")],
                [InlineKeyboardButton("💎 Оплатить звездочками", url=f"https://t.me/{self.config.STARS_USERNAME}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(contact_text, reply_markup=reply_markup)
            logger.info(f"✅ Контактная информация показана пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в contact_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def referral_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Реферальная система' с ОРИГИНАЛЬНЫМИ кнопками"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: referral callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            referral_text = """👥 РЕФЕРАЛЬНАЯ СИСТЕМА

Приглашайте друзей и получайте бонусы!
💰 За каждого приглашенного друга вы получаете комиссию

💡 Хотите узнать свой реферальный код и ссылку?"""

            # ОРИГИНАЛЬНЫЕ КНОПКИ
            keyboard = [
                [InlineKeyboardButton("📋 Получить реферальную ссылку", callback_data="get_referral")],
                [InlineKeyboardButton("📊 Моя статистика", callback_data="referral_stats")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(referral_text, reply_markup=reply_markup)
            logger.info(f"✅ Реферальная система показана пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def get_referral_link_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик получения реферальной ссылки - БЕЗ ЖИРНОГО ТЕКСТА"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: get_referral callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            user_id = update.effective_user.id
            referral_code = f"ref_{user_id}"
            bot_username = self.config.BOT_USERNAME
            referral_link = f"https://t.me/{bot_username}?start={referral_code}"

            referral_info = f"""📋 ВАША РЕФЕРАЛЬНАЯ ССЫЛКА:

{referral_link}

💡 Отправьте эту ссылку друзьям!
💰 За каждого приглашенного вы получите комиссию"""

            # Кнопка "Скопировать ссылку"
            keyboard = [
                [InlineKeyboardButton("📋 Скопировать ссылку", callback_data=f"copy_referral_{user_id}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="referral")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(referral_info, reply_markup=reply_markup)
            logger.info(f"✅ Реферальная ссылка показана пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в get_referral_link_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def referral_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик статистики рефералов"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: referral_stats callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            user_id = update.effective_user.id
            stats = self.get_user_referral_stats(user_id)

            if stats:
                stats_text = f"""📊 ВАША РЕФЕРАЛЬНАЯ СТАТИСТИКА:

👥 Всего рефералов: {stats['total_referrals']}
💰 Всего заработано: {stats['total_earnings']:.2f} TON

💡 Приглашайте больше друзей для увеличения заработка!"""
            else:
                stats_text = """📊 ВАША РЕФЕРАЛЬНАЯ СТАТИСТИКА:

👥 Всего рефералов: 0
💰 Всего заработано: 0.00 TON

💡 Начните приглашать друзей!"""

            # Кнопка "Получить ссылку"
            keyboard = [
                [InlineKeyboardButton("📋 Получить ссылку", callback_data="get_referral")],
                [InlineKeyboardButton("🔙 Назад", callback_data="referral")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(stats_text, reply_markup=reply_markup)
            logger.info(f"✅ Реферальная статистика показана пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_stats_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def copy_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик копирования TON адреса"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: copy_ton callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Формируем сообщение с адресом кошелька
            address_message = f"""💰 АДРЕС КОШЕЛЬКА:

<code>{self.config.TON_WALLET_ADDRESS}</code>

⚠️ Скопируйте адрес выше и используйте его для оплаты!"""

            # Кнопка "Назад к оплате"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад к оплате", callback_data=f"payment_{update.message.text.split()[-1] if update.message and update.message.text else ''}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(address_message, reply_markup=reply_markup, parse_mode='HTML')
            logger.info(f"✅ Адрес кошелька показан пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в copy_ton_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Назад' - возврат к главному меню"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: back callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Возвращаемся к главному меню
            main_menu_text = """🤖 Добро пожаловать в PassiveNFT Bot!

💰 Получайте пассивный доход от NFT проектов
👥 Присоединяйтесь к растущему сообществу
⭐ Пользуйтесь нашими услугами удобно и просто

Выберите действие:"""

            keyboard = [
                [InlineKeyboardButton("💳 Подписки", callback_data="subscription")],
                [InlineKeyboardButton("💬 Связь", callback_data="contact")],
                [InlineKeyboardButton("👥 Реферальная система", callback_data="referral")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(main_menu_text, reply_markup=reply_markup)
            logger.info(f"✅ Возврат к главному меню для пользователя {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraa"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: /adminserveraa от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к админ панели")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к админ панели от пользователя {user.id}")
                return

            # Формируем меню админ панели
            admin_menu = """🔧 АДМИН ПАНЕЛЬ

Выберите действие:"""

            keyboard = [
                [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
                [InlineKeyboardButton("👥 Люди", callback_data="admin_people")],
                [InlineKeyboardButton("👤 Рефералы", callback_data="admin_referrals")],
                [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(admin_menu, reply_markup=reply_markup)
            logger.info(f"✅ Админ панель отправлена пользователю {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в admin_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def admin_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraastat"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: /adminserveraastat от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к админ панели")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к админ панели от пользователя {user.id}")
                return

            # Получаем статистику
            try:
                stats_text = self.get_subscription_stats()
                await update.message.reply_text(f"📊 СТАТИСТИКА:\n\n{stats_text}")
                logger.info(f"✅ Статистика отправлена пользователю {user.id}")
            except Exception as e:
                logger.error(f"Ошибка получения статистики: {e}")
                await update.message.reply_text("❌ Ошибка при получении статистики")
        except Exception as e:
            logger.error(f"❌ Ошибка в admin_stats_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def admin_people_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraapeople"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: /adminserveraapeople от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к админ панели")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к админ панели от пользователя {user.id}")
                return

            # Получаем список участников
            try:
                people_text = self.get_subscribed_people()
                await update.message.reply_text(f"👥 Список участников:\n\n{people_text}")
                logger.info(f"✅ Список участников отправлен пользователю {user.id}")
            except Exception as e:
                logger.error(f"Ошибка получения списка людей: {e}")
                await update.message.reply_text("❌ Ошибка при получении списка участников")
        except Exception as e:
            logger.error(f"❌ Ошибка в admin_people_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def admin_referrals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraaref"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: /adminserveraaref от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к админ панели")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к админ панели от пользователя {user.id}")
                return

            # Получаем реферальную статистику
            try:
                referral_stats_text = self.get_referrals_stats()
                await update.message.reply_text(f"👥 РЕФЕРАЛЬНАЯ СТАТИСТИКА:\n\n{referral_stats_text}")
                logger.info(f"✅ Реферальная статистика отправлена пользователю {user.id}")
            except Exception as e:
                logger.error(f"Ошибка получения реферальной статистики: {e}")
                await update.message.reply_text("❌ Ошибка при получении реферальной статистики")
        except Exception as e:
            logger.error(f"❌ Ошибка в admin_referrals_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /broadcast для рассылки сообщений всем пользователям"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: /broadcast от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к админ панели")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к админ панели от пользователя {user.id}")
                return

            # Получаем сообщение из аргументов команды
            if not context.args:
                await update.message.reply_text("❌ Укажите текст для рассылки после команды /broadcast")
                return

            message_text = ' '.join(context.args)
            
            # Получаем список всех пользователей
            users = self.get_all_users()
            
            success_count = 0
            failed_count = 0
            
            for user_info in users:
                try:
                    await self.application.bot.send_message(
                        chat_id=user_info['user_id'],
                        text=f"📢 ОБЪЯВЛЕНИЕ:\n\n{message_text}"
                    )
                    success_count += 1
                    logger.info(f"Сообщение отправлено пользователю {user_info['user_id']}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Ошибка отправки сообщения пользователю {user_info['user_id']}: {e}")

            await update.message.reply_text(
                f"📢 Рассылка завершена:\n✅ Отправлено: {success_count}\n❌ Ошибок: {failed_count}"
            )
            logger.info(f"✅ Рассылка завершена: {success_count} отправлено, {failed_count} ошибок")
        except Exception as e:
            logger.error(f"❌ Ошибка в broadcast_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка при рассылке. Попробуйте позже.")

    def get_all_users(self):
        """Получение списка всех пользователей из базы данных"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                # Сначала проверяем, есть ли таблица users
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                if cursor.fetchone():
                    cursor.execute("SELECT user_id, username, first_name FROM users ORDER BY registration_date DESC")
                    users = cursor.fetchall()
                    return [{'user_id': user[0], 'username': user[1], 'first_name': user[2]} for user in users]
                else:
                    # Если таблицы users нет, берем из subscriptions как раньше
                    cursor.execute("SELECT DISTINCT user_id FROM subscriptions")
                    users = cursor.fetchall()
                    return [{'user_id': user[0]} for user in users]
        except Exception as e:
            logger.error(f"Ошибка получения списка пользователей: {e}")
            return []

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        logger.info(f"🎯 ТЕКСТОВОЕ СООБЩЕНИЕ ПОЛУЧЕНО: '{update.message.text}' от пользователя {update.effective_user.id}")
        try:
            message = update.message.text.lower()
            if "admin" in message and update.effective_user.id in self.config.ADMIN_USER_IDS:
                await self.admin_command(update, context)
                return

            # Ответ на неизвестные команды
            await update.message.reply_text("🤖 Используйте /start для начала работы")
        except Exception as e:
            logger.error(f"❌ Ошибка в handle_message: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    def get_user_referral_stats(self, user_id: int):
        """Получение статистики рефералов пользователя"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT total_referrals, total_earnings FROM referrals WHERE referrer_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                if result:
                    return {
                        'total_referrals': result[0],
                        'total_earnings': result[1]
                    }
                return None
        except Exception as e:
            logger.error(f"Ошибка получения статистики рефералов: {e}")
            return None

    def get_subscription_stats(self) -> str:
        """Получение общей статистики подписок для админа"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Получаем статистику по подпискам
                cursor.execute("""
                    SELECT subscription_type, COUNT(*) as count
                    FROM subscriptions
                    WHERE active = 1
                    GROUP BY subscription_type
                """)
                results = cursor.fetchall()
                
                total_active = sum(count for _, count in results)
                stats = []
                
                for sub_type, count in results:
                    plan_name = self.config.SUBSCRIPTION_PLANS[int(sub_type)]['name']
                    stats.append(f"• {plan_name}: {count}")
                
                return f"Всего активных подписок: {total_active}\n" + "\n".join(stats)
        except Exception as e:
            logger.error(f"Ошибка получения статистики подписок: {e}")
            return "Ошибка при получении статистики"

    def get_subscribed_people(self) -> str:
        """Получение списка участников для админа"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Сначала пробуем получить пользователей с подписками
                cursor.execute("""
                    SELECT s.user_id, s.subscription_type, s.start_date, s.active, u.username, u.first_name 
                    FROM subscriptions s 
                    LEFT JOIN users u ON s.user_id = u.user_id 
                    WHERE s.active = 1 
                    LIMIT 20
                """)
                subscriptions = cursor.fetchall()
                
                # Затем получаем всех зарегистрированных пользователей
                cursor.execute("""
                    SELECT u.user_id, u.username, u.first_name, u.registration_date, u.referral_code
                    FROM users u
                    ORDER BY u.registration_date DESC
                    LIMIT 50
                """)
                all_users = cursor.fetchall()
                
                result_lines = []
                
                # Сначала показываем пользователей с активными подписками
                if subscriptions:
                    result_lines.append("👥 ПОЛЬЗОВАТЕЛИ С ПОДПИСКАМИ:")
                    result_lines.append("=" * 40)
                    for sub in subscriptions:
                        user_id, sub_type, start_date, active, username, first_name = sub
                        plan_name = self.config.SUBSCRIPTION_PLANS[int(sub_type)]['name']
                        display_name = username or first_name or f"User{user_id}"
                        status = "✅ Активна" if active else "❌ Неактивна"
                        result_lines.append(f"ID: {user_id}\nНик: @{display_name}\nПодписка: {plan_name}\nС: {start_date}\n{status}\n")
                
                # Затем показываем всех зарегистрированных пользователей
                if all_users:
                    if result_lines:
                        result_lines.append("\n" + "=" * 40)
                        result_lines.append("📝 ВСЕ ЗАРЕГИСТРИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ:")
                        result_lines.append("=" * 40)
                    else:
                        result_lines.append("📝 ЗАРЕГИСТРИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ:")
                        result_lines.append("=" * 40)
                    
                    for user in all_users:
                        user_id, username, first_name, reg_date, referral_code = user
                        display_name = username or first_name or f"User{user_id}"
                        result_lines.append(f"ID: {user_id}\nНик: @{display_name}\nРегистрация: {reg_date}\nКод: {referral_code}\n")
                
                if not result_lines:
                    return "Нет данных о пользователях"
                
                return "\n".join(result_lines)
        except Exception as e:
            logger.error(f"Ошибка получения списка людей: {e}")
            return f"Ошибка при получении списка: {str(e)}"

    def get_referrals_stats(self) -> str:
        """Получение реферальной статистики для админа"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Получаем топ рефереров
                cursor.execute("""
                    SELECT referrer_id, total_referrals, total_earnings
                    FROM referrals
                    ORDER BY total_referrals DESC
                    LIMIT 10
                """)
                results = cursor.fetchall()
                
                total_referrals = sum(result[1] for result in results)
                top_list = []
                
                for referrer_id, referrals, earnings in results:
                    top_list.append(f"• ID {referrer_id}: {referrals} рефералов, {earnings:.2f} TON")
                
                return f"Общее количество рефералов: {total_referrals}\n\nТОП рефереров:\n" + "\n".join(top_list)
        except Exception as e:
            logger.error(f"Ошибка получения реферальной статистики: {e}")
            return "Ошибка при получении реферальной статистики"

    async def run(self):
        """Запуск бота с улучшенной структурой"""
        logger.info("🚀 Запуск PassiveNFT Bot на Render...")
        logger.info(f"🤖 Бот: @{self.config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...{self.config.TON_WALLET_ADDRESS[-10:]}")
        logger.info("✅ Реферальная система включена")
        
        try:
            # Очистка webhook перед запуском
            await self.clear_webhook_on_startup()
            
            # Запуск бота
            await self.application.initialize()
            await self.application.start()
            logger.info("✅ Бот инициализирован")
            
            # Запуск polling
            await self.application.updater.start_polling(
                timeout=10,
                drop_pending_updates=True,
                allowed_updates=["message", "edited_message", "callback_query"]
            )
            logger.info("✅ Бот начал получать обновления")
            
            # Ожидание завершения
            await self.application.updater.idle()
            
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            try:
                if self.application:
                    await self.application.shutdown()
                    logger.info("✅ Бот корректно остановлен")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при остановке бота: {e}")

async def main():
    """Главная функция запуска с улучшенной обработкой ошибок"""
    try:
        logger.info("🎯 Инициализация PassiveNFT Bot...")
        bot = PassiveNFTBot()
        logger.info("✅ Bot инициализирован, начинаем запуск...")
        await bot.run()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в main: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

# ФУНКЦИЯ ВЕБ-СЕРВЕРА ДЛЯ RENDER.COM
async def start_web_server():
    """Простой HTTP сервер для удовлетворения требований Render.com"""
    async def health_check(request):
        return web.Response(text="Bot is running", status=200)
    
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get('PORT', 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🚀 Web server started on port {port}")

async def run_both():
    """Запускает бота и веб-сервер одновременно с улучшенной обработкой ошибок"""
    bot_instance = PassiveNFTBot()
    try:
        await asyncio.gather(
            bot_instance.run(),  # Бот
            start_web_server()   # Веб-сервер
        )
    except KeyboardInterrupt:
        logger.info("🛑 Приложение остановлено пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в run_both: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(run_both())
    except KeyboardInterrupt:
        print("🛑 Приложение остановлено")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        raise
