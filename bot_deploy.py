#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PassiveNFT Bot - ВЕРСИЯ БЕЗ ЖИРНОГО ТЕКСТА (для устранения ошибок парсинга)
"""
import asyncio
import logging
import sqlite3
import sys
import traceback
from pathlib import Path

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
                conn.commit()
            logger.info("База данных инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise

class SafeConfig:
    """Безопасная конфигурация бота без жирного текста"""
    def __init__(self):
        # Основные настройки
        self.BOT_TOKEN = self._get_env_var('BOT_TOKEN', '8530441136:AAHto3A4Zqa5FnGG01cxL6SvU3jW8_Ai0iI')
        self.ADMIN_USER_IDS = [8387394503] # pro.player.egor

        # Настройки TON кошелька
        self.TON_WALLET_ADDRESS = self._get_env_var('TON_WALLET_ADDRESS', 'UQAij8pQ3HhdBn3lw6n9Iy2toOH9OMcBuL8yoSXTNpLJdfZJ')
        self.MANAGER_USERNAME = self._get_env_var('MANAGER_USERNAME', 'num6er9')
        self.BOT_USERNAME = self._get_env_var('BOT_USERNAME', 'PassiveNFT')

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
                "price_ton": 13
            }
        ]

        # ТЕКСТЫ БЕЗ ЖИРНОГО ФОРМАТИРОВАНИЯ
        self.WELCOME_MESSAGE = """🎉 welcome to the PassiveNFT 🎉

💰 PassiveNFT это возможность ПРИУМНОЖИТЬ свои вложения вплоть до х10! 💰

📋 ознакомиться со стоимостью подписок и что в них входит вы можете по кнопке "Подписки".

❓ если у вас всё еще остались вопросы, нажмите кнопку "Связь" для обращения к менеджеру по вопросам."""

        # 2. ОБЩЕЕ ОПИСАНИЕ ПОДПИСОК (Пункт 2.1)
        self.SUBSCRIPTION_DESCRIPTION = "💳 Нажми на интересующую тебя подписку"

        # 3. ТЕКСТ СВЯЗИ (Пункт 3)
        self.CONTACT_MESSAGE = f"""💬 Если у вас возникли какие-либо трудности с оплатой или есть вопросы на которые здесь нет ответов, нажмите [сюда](https://t.me/{self.MANAGER_USERNAME}) для обращения к менеджеру по вопросам."""

        # 4. РЕФЕРАЛЬНАЯ СИСТЕМА - ГЛАВНОЕ МЕНЮ (Пункт 4)
        self.REFERRAL_MESSAGE = f"""👥 Реферальная система предназначена для амбассадоров закрытого проекта PassiveNFT и обычных участников
🔗 Она состоит из пригласительной ссылки, где владелец ссылки получается 10% с его оплаты подписки, для более точных подробностей свяжитесь с [менеджером](https://t.me/{self.MANAGER_USERNAME})"""

        # 5. РЕФЕРАЛЬНАЯ ССЫЛКА
        self.REFERRAL_LINK_MESSAGE = "Ваша персональная реферальная ссылка:"

        # 6. СТАТИСТИКА РЕФЕРАЛОВ
        self.REFERRAL_STATS_MESSAGE = """Статистика ваших рефералов:

{referrals_info}"""

        # 7. СООБЩЕНИЕ ОБ ОПЛАТЕ
        self.PAYMENT_INSTRUCTIONS = f"""Для оплаты отправьте {self.TON_WALLET_ADDRESS} на указанный выше адрес TON кошелька.
⚠️ ВАЖНО: Скопируйте адрес кошелька и отправьте указанную сумму TON."""

        # НОВЫЕ ТЕКСТЫ ДЛЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ
        self.REFERRAL_WELCOME_MESSAGE = """🎉 welcome to the PassiveNFT 🎉

💰 PassiveNFT это возможность ПРИУМНОЖИТЬ свои вложения вплоть до х10! 💰

🔗 Вы пришли по реферальной ссылке! После оплаты ваш реферер получит 10% бонус.

📋 ознакомиться со стоимостью подписок и что в них входит вы можете по кнопке "Подписки".

❓ если у вас всё еще остались вопросы, нажмите кнопку "Связь" для обращения к менеджеру по вопросам."""

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
    config = SafeConfig()
    logger.info("✅ Безопасная конфигурация загружена")
    logger.info(f"🤖 Бот: @{config.BOT_USERNAME}")
    logger.info(f"💰 Кошелек: {config.TON_WALLET_ADDRESS[:10]}...{config.TON_WALLET_ADDRESS[-10:]}")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки конфигурации: {e}")
    config = SafeConfig()


class PassiveNFTBot:
    """Главный класс бота без жирного текста"""
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
            self.application.add_handler(CommandHandler("confirm_payment", self.confirm_payment_command))
            self.application.add_handler(CommandHandler("adminserveraa", self.admin_command))
            self.application.add_handler(CommandHandler("adminserveraastat", self.admin_stats_command))
            self.application.add_handler(CommandHandler("adminserveraapeople", self.admin_people_command))
            self.application.add_handler(CommandHandler("adminserveraaref", self.admin_referrals_command))
            self.application.add_handler(CallbackQueryHandler(self.subscription_callback, pattern="^subscription$"))
            self.application.add_handler(CallbackQueryHandler(self.subscription_plan_callback, pattern="^subscription_plan_"))
            self.application.add_handler(CallbackQueryHandler(self.payment_callback, pattern="^payment_"))
            self.application.add_handler(CallbackQueryHandler(self.contact_callback, pattern="^contact$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_callback, pattern="^referral$"))
            self.application.add_handler(CallbackQueryHandler(self.get_referral_link_callback, pattern="^get_referral$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_stats_callback, pattern="^referral_stats$"))
            self.application.add_handler(CallbackQueryHandler(self.back_callback, pattern="^back$"))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

            logger.info("Telegram приложение настроено")
        except Exception as e:
            logger.error(f"Ошибка настройки приложения: {e}")
            raise

    async def clear_webhook_on_startup(self):
        """Очистка webhook перед запуском для решения конфликтов"""
        try:
            logger.info("🧹 Очистка старых webhook'ов...")
            await self.application.bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook очищен успешно")
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при очистке webhook: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start с обработкой реферальных параметров"""
        user = update.effective_user
        args = context.args
        
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
        await update.message.reply_text(welcome_text)

    async def confirm_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды подтверждения оплаты и добавления реферала"""
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
                
                # Проверяем, что пользователь еще не добавлен как реферал
                cursor.execute(
                    "SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND referral_code = ?",
                    (referrer_id, str(referred_user_id))
                )
                if cursor.fetchone()[0] > 0:
                    logger.info(f"Реферал {referred_user_id} для {referrer_id} уже существует")
                    return True  # Уже существует, считаем успехом
                
                # Добавляем нового реферала
                cursor.execute(
                    "INSERT OR REPLACE INTO referrals (referrer_id, referral_code, total_referrals, total_earnings) VALUES (?, ?, ?, ?)",
                    (referrer_id, str(referred_user_id), 1, 0.0)
                )
                
                # Обновляем статистику реферера
                cursor.execute(
                    "UPDATE referrals SET total_referrals = total_referrals + 1 WHERE referrer_id = ?",
                    (referrer_id,)
                )
                
                conn.commit()
                logger.info(f"Добавлен реферал {referred_user_id} для реферера {referrer_id}")
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления реферала: {e}")
            return False

    async def subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Подписки' - БЕЗ ЖИРНОГО ТЕКСТА"""
        query = update.callback_query
        await query.answer()

        # ОРИГИНАЛЬНОЕ общее описание подписок
        subscription_text = self.config.SUBSCRIPTION_DESCRIPTION

        # ОРИГИНАЛЬНЫЕ кнопки подписок
        keyboard = []
        for i, plan in enumerate(self.config.SUBSCRIPTION_PLANS):
            button_text = plan['name']
            callback_data = f"subscription_plan_{i}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        # Кнопка "Назад"
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.message.edit_text(subscription_text, reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer("Подписки уже открыты!")
            else:
                await query.answer("Ошибка при открытии подписок.")

    async def subscription_plan_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора конкретной подписки с ОРИГИНАЛЬНЫМ описанием"""
        query = update.callback_query
        await query.answer()

        plan_index = int(query.data.split('_')[2])
        plan = self.config.SUBSCRIPTION_PLANS[plan_index]

        # ОРИГИНАЛЬНОЕ описание подписки
        plan_text = plan['description']

        # ОРИГИНАЛЬНЫЕ кнопки: "Оплатить" и "Назад"
        keyboard = [
            [InlineKeyboardButton("💳 Оплатить", callback_data=f"payment_{plan_index}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(plan_text, reply_markup=reply_markup)

    async def payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Оплатить' - БЕЗ ЖИРНОГО ТЕКСТА"""
        query = update.callback_query
        await query.answer()

        plan_index = int(query.data.split('_')[1])
        plan = self.config.SUBSCRIPTION_PLANS[plan_index]

        # БЕЗ ЖИРНОГО ТЕКСТА - чистый текст
        payment_text = f"""💰 ОПЛАТА: {plan['price_ton']} TON

Адрес кошелька:
{self.config.TON_WALLET_ADDRESS}

⚠️ ВАЖНО: Скопируйте адрес кошелька и отправьте указанную сумму TON.

После оплаты обратитесь к менеджеру @{self.config.MANAGER_USERNAME} для подтверждения подписки.

💡 Если вы пришли по реферальной ссылке, используйте команду /confirm_payment после оплаты."""

        # Кнопка "Назад"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=f"subscription_plan_{plan_index}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(payment_text, reply_markup=reply_markup)

    async def contact_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Связь' с ОРИГИНАЛЬНЫМ текстом"""
        query = update.callback_query
        await query.answer()

        # ОРИГИНАЛЬНЫЙ текст связи с ссылкой
        contact_text = self.config.CONTACT_MESSAGE

        # Кнопка "Назад"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.message.edit_text(contact_text, reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer("Контакты уже открыты!")
            else:
                await query.answer("Ошибка при открытии контактов.")

    async def referral_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Реферальная система' с ОРИГИНАЛЬНЫМИ кнопками"""
        query = update.callback_query
        await query.answer()

        # ОРИГИНАЛЬНЫЙ текст реферальной системы
        referral_text = self.config.REFERRAL_MESSAGE

        # ОРИГИНАЛЬНЫЕ кнопки: "Назад", "Получить реферальную ссылку", "Статистика рефералов"
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="back")],
            [InlineKeyboardButton("🔗 Получить реферальную ссылку", callback_data="get_referral")],
            [InlineKeyboardButton("📊 Статистика рефералов", callback_data="referral_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.message.edit_text(referral_text, reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
            # Сообщение не изменилось, просто отвечаем на callback
            await query.answer()

    async def get_referral_link_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик получения реферальной ссылки - БЕЗ ЖИРНОГО ТЕКСТА"""
        query = update.callback_query
        await query.answer()
        user = query.from_user

        # Генерация персональной реферальной ссылки
        referral_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
        referral_link_text = f"{self.config.REFERRAL_LINK_MESSAGE}\n\n{referral_link}"

        # Кнопка "Назад"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="referral")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(referral_link_text, reply_markup=reply_markup)

    async def referral_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик статистики рефералов"""
        query = update.callback_query
        await query.answer()

        # Получение статистики пользователя
        stats = self.get_user_referral_stats(query.from_user.id)
        if stats:
            stats_text = self.config.REFERRAL_STATS_MESSAGE.format(referrals_info=stats)
        else:
            stats_text = "У вас пока нет рефералов."

        # Кнопка "Назад"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="referral")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(stats_text, reply_markup=reply_markup)

    async def back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Назад' - возврат к главному меню"""
        query = update.callback_query
        await query.answer()

        # Возврат к ОРИГИНАЛЬНОМУ приветственному сообщению
        welcome_text = self.config.WELCOME_MESSAGE

        # ОРИГИНАЛЬНЫЕ кнопки главного меню
        keyboard = [
            [InlineKeyboardButton("💳 Подписки", callback_data="subscription")],
            [InlineKeyboardButton("💬 Связь", callback_data="contact")],
            [InlineKeyboardButton("👥 Реферальная система", callback_data="referral")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.message.edit_text(welcome_text, reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
            # Сообщение не изменилось, просто отвечаем на callback
            await query.answer()

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = f"""🤖 PassiveNFT Bot - Справка
/start - Начать работу с ботом
/help - Показать эту справку
/confirm_payment - Подтвердить оплату и добавить реферала
/adminserveraa - Админ панель (только для админов)
💬 Для вопросов: @{self.config.MANAGER_USERNAME}"""
        await update.message.reply_text(help_text)

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraa"""
        user = update.effective_user

        # Проверяем, является ли пользователь админом
        if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
            await update.message.reply_text("❌ У вас нет доступа к админ панели")
            return

        # ОРИГИНАЛЬНЫЙ текст админ панели
        admin_text = """🔧 Админ панель PassiveNFT Bot
📊 /adminserveraastat - статистика подписок
👥 /adminserveraapeople - список участников
🔗 /adminserveraaref - реферальная статистика
💳 Количество подписок:
👥 на 150 человек: энное количество из 150
👥 на 100 человек: энное количество из 100
👥 на 50 человек: энное количество из 50"""
        await update.message.reply_text(admin_text)

    async def admin_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraastat"""
        user = update.effective_user

        # Проверяем, является ли пользователь админом
        if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
            await update.message.reply_text("❌ У вас нет доступа к админ панели")
            return

        # Получаем статистику подписок
        try:
            stats_text = self.get_subscription_stats()
            await update.message.reply_text(f"📊 Статистика подписок:\n\n{stats_text}")
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            await update.message.reply_text("❌ Ошибка при получении статистики")

    async def admin_people_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraapeople"""
        user = update.effective_user

        # Проверяем, является ли пользователь админом
        if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
            await update.message.reply_text("❌ У вас нет доступа к админ панели")
            return

        # Получаем список участников
        try:
            people_text = self.get_subscribed_people()
            await update.message.reply_text(f"👥 Список участников:\n\n{people_text}")
        except Exception as e:
            logger.error(f"Ошибка получения списка людей: {e}")
            await update.message.reply_text("❌ Ошибка при получении списка участников")

    async def admin_referrals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraaref"""
        user = update.effective_user

        # Проверяем, является ли пользователь админом
        if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
            await update.message.reply_text("❌ У вас нет доступа к админ панели")
            return

        # Получаем реферальную статистику
        try:
            referrals_text = self.get_referrals_stats()
            await update.message.reply_text(f"🔗 Реферальная статистика:\n\n{referrals_text}")
        except Exception as e:
            logger.error(f"Ошибка получения реферальной статистики: {e}")
            await update.message.reply_text("❌ Ошибка при получении реферальной статистики")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        message = update.message.text.lower()
        if "help" in message or "помощь" in message:
            await self.help_command(update, context)
        elif "admin" in message and update.effective_user.id in self.config.ADMIN_USER_IDS:
            await self.admin_command(update, context)
        else:
            await update.message.reply_text(
                "🤖 Используйте /start для начала работы или /help для справки"
            )

    def get_user_referral_stats(self, user_id: int):
        """Получение статистики рефералов пользователя"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
                    (user_id,)
                )
                count = cursor.fetchone()[0]
                if count > 0:
                    return f"Количество рефералов: {count}"
                return None
        except Exception as e:
            logger.error(f"Ошибка получения статистики рефералов: {e}")
            return None

    def get_subscription_stats(self) -> str:
        """Получение общей статистики подписок для админа"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Общее количество подписок
                cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE active = 1")
                total_active = cursor.fetchone()[0]
                
                # Количество по каждому типу подписки
                stats = []
                for i, plan in enumerate(self.config.SUBSCRIPTION_PLANS):
                    cursor.execute(
                        "SELECT COUNT(*) FROM subscriptions WHERE subscription_type = ? AND active = 1",
                        (str(i),)
                    )
                    count = cursor.fetchone()[0]
                    stats.append(f"• {plan['name']}: {count} человек")
                
                return f"Всего активных подписок: {total_active}\n" + "\n".join(stats)
        except Exception as e:
            logger.error(f"Ошибка получения статистики подписок: {e}")
            return "Ошибка при получении статистики"

    def get_subscribed_people(self) -> str:
        """Получение списка участников для админа"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT user_id, subscription_type, start_date, active FROM subscriptions WHERE active = 1 LIMIT 20"
                )
                subscriptions = cursor.fetchall()
                
                if not subscriptions:
                    return "Нет активных подписок"
                
                people_list = []
                for sub in subscriptions:
                    user_id, sub_type, start_date, active = sub
                    plan_name = self.config.SUBSCRIPTION_PLANS[int(sub_type)]['name']
                    status = "✅ Активна" if active else "❌ Неактивна"
                    people_list.append(f"ID: {user_id}\nПодписка: {plan_name}\nС: {start_date}\n{status}\n")
                
                return "\n".join(people_list) if people_list else "Нет данных"
        except Exception as e:
            logger.error(f"Ошибка получения списка людей: {e}")
            return "Ошибка при получении списка"

    def get_referrals_stats(self) -> str:
        """Получение реферальной статистики для админа"""
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Общее количество рефералов
                cursor.execute("SELECT COUNT(*) FROM referrals")
                total_referrals = cursor.fetchone()[0]
                
                # ТОП рефереров
                cursor.execute(
                    "SELECT referrer_id, total_referrals, total_earnings FROM referrals ORDER BY total_referrals DESC LIMIT 10"
                )
                top_referrers = cursor.fetchall()
                
                if not top_referrers:
                    return f"Общее количество рефералов: {total_referrals}\n\nНет данных о реферерах"
                
                top_list = []
                for ref_id, ref_count, earnings in top_referrers:
                    top_list.append(f"ID: {ref_id} - Рефералов: {ref_count} - Доход: {earnings} TON")
                
                return f"Общее количество рефералов: {total_referrals}\n\nТОП рефереров:\n" + "\n".join(top_list)
        except Exception as e:
            logger.error(f"Ошибка получения реферальной статистики: {e}")
            return "Ошибка при получении реферальной статистики"

    async def run(self):
        """Запуск бота с исправленным методом"""
        logger.info("🚀 Запуск PassiveNFT Bot на Render...")
        logger.info(f"🤖 Бот: @{self.config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...{self.config.TON_WALLET_ADDRESS[-10:]}")
        logger.info("✅ Реферальная система включена")

        # Очистка webhook перед запуском
        await self.clear_webhook_on_startup()

        # Инициализация и запуск приложения
        await self.application.initialize()
        await self.application.start()

        try:
            # Запуск polling
            await self.application.updater.start_polling()
            logger.info("✅ Бот запущен и ожидает команды...")
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

# ФУНКЦИЯ ВЕБ-СЕРВЕРА ДЛЯ RENDER.COM
async def start_web_server():
    """Простой HTTP сервер для удовлетворения требований Render.com"""
    async def health_check(request):
        return web.Response(text="Bot is running", status=200)
    
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    port = int(os.environ.get('PORT', 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🚀 Web server started on port {port}")

if __name__ == "__main__":
    async def run_both():
        """Запускает бота и веб-сервер одновременно"""
        bot_instance = PassiveNFTBot()
        await asyncio.gather(
            bot_instance.run(),  # Бот
            start_web_server()   # Веб-сервер
        )
    
    try:
        asyncio.run(run_both())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        sys.exit(1)
