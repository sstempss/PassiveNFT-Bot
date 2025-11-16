#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PassiveNFT Bot - Оригинальные тексты восстановлены
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
                conn.commit()
            logger.info("База данных инициализирована")
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise

class SafeConfig:
    """Безопасная конфигурация бота с ОРИГИНАЛЬНЫМИ текстами"""
    def __init__(self):
        # Основные настройки
        self.BOT_TOKEN = self._get_env_var('BOT_TOKEN', '8530441136:AAHto3A4Zqa5FnGG01cxL6SvU3jW8_Ai0iI')
        self.ADMIN_USER_IDS = [8387394503] # pro.player.egor
        # Настройки TON кошелька
        self.TON_WALLET_ADDRESS = self._get_env_var('TON_WALLET_ADDRESS', 'UQAij8pQ3HhdBn3lw6n9Iy2toOH9OMcBuL8yoSXTNpLJdfZJ')
        self.MANAGER_USERNAME = self._get_env_var('MANAGER_USERNAME', 'num6er9')
        self.BOT_USERNAME = self._get_env_var('BOT_USERNAME', 'PassiveNFT')
        
        # Настройки подписок - ДЕТАЛЬНЫЕ ОПИСАНИЯ КАЖДОГО ПЛАНА
        self.SUBSCRIPTION_PLANS = [
            {
                "name": "👥 На 150 человек",
                "price": "4",
                "description": """150 NFT в месяц, 120 гифтов в месяц

📊 Процент победы одного участника составляет 0,67% на одно NFT, количество разыгрываемых NFT в день – 5, следственно 5*0,67% = 3,35% на победу за день, в месяц получается 100,5%

🎁 На гифты за звезды процент победы на одного участника составляет 0,67%, количество разыгрываемых гифтов в день – 4, следственно 4*0,67% = 2,68% на победу за день, в месяц получается 80,4%

💰 ~ окуп от х1 до х5"""
            },
            {
                "name": "👥 На 100 человек", 
                "price": "7",
                "description": """50 NFT в месяц, 120 гифтов в месяц

📊 Процент победы одного участника составляет 0,67% на одно NFT, количество разыгрываемых NFT в день – 5, следственно 5*0,67% = 3,35% на победу за день, в месяц получается 100,5%

🎁 На гифты за звезды процент победы на одного участника составляет 0,67%, количество разыгрываемых гифтов в день – 4, следственно 4*0,67% = 2,68% на победу за день, в месяц получается 80,4%

💰 ~ окуп от х1 до х5"""
            },
            {
                "name": "👥 На 50 человек",
                "price": "13",
                "description": """210 NFT в месяц, 120 гифтов в месяц

📊 Процент победы одного участника составляет 1% на одно NFT, количество разыгрываемых NFT в день – 7, следственно 7*2% = 14% на победу за день, в месяц получается 420%

🎁 На гифты за звезды процент победы на одного участника составляет 2%, количество разыгрываемых гифтов в день – 4, следственно 4*2% = 8% на победу за день, в месяц получается 240%

💰 На одного участника в ТГК получается возврат средств в 70% от стоимости подписки в месяц (в размере 4 NFT+ 2 гифта за 50 зв.)

💰 ~ окуп от х1 до х2,5-3"""
            }
        ]
        
        # ОРИГИНАЛЬНЫЕ ТЕКСТЫ БОТА
        self.WELCOME_MESSAGE = """🎉 welcome to the PassiveNFT 🎉
💰 !PassiveNFT это возможность ПРИУМНОЖИТЬ свои вложения вплоть до х10! 

📋 ознакомиться со стоимостью подписок и что в них входит вы можете по кнопке "Подписки".
❓ если у вас всё еще остались вопросы, нажмите кнопку "Связь" для обращения к менеджеру по вопросам."""
        
        # 2. ОБЩЕЕ ОПИСАНИЕ ПОДПИСОК (Пункт 2.1)
        self.SUBSCRIPTION_DESCRIPTION = """💳 Подписки PassiveNFT

🎯 В каждую подписку входит:

📊 Вход в ТГК для возможности пассивного получения NFT
🔒 Полная безопасность ваших средств
📈 Пассивный доход без активных действий (почти :))

💰 Ценовая политика:
👥 На 150 человек - 4 TON (150 мест)
👥 На 100 человек - 7 TON (100 мест)
👥 На 50 человек - 13 TON (50 мест)

Выберите подходящий тарифный план:"""
        
        # 3. ТЕКСТ СВЯЗИ (Пункт 3)
        self.CONTACT_MESSAGE = f"""💬 Если у вас возникли какие-либо трудности с оплатой или есть вопросы на которые здесь нет ответов, нажмите [сюда](https://t.me/{self.MANAGER_USERNAME}) для обращения к менеджеру по вопросам."""
        
        # 4. РЕФЕРАЛЬНАЯ СИСТЕМА - ГЛАВНОЕ МЕНЮ (Пункт 4)
        self.REFERRAL_MESSAGE = f"""👥 Реферальная система предназначена для амбассадоров закрытого проекта PassiveNFT и обычных участников
🔗 Она состоит из пригласительной ссылки, где владелец ссылки получается 10% с его оплаты подписки, для более точных подробностей свяжитесь с [менеджером](https://t.me/{self.MANAGER_USERNAME})"""
        
        # 5. РЕФЕРАЛЬНАЯ ССЫЛКА
        self.REFERRAL_LINK_MESSAGE = "Ваша персональная реферальная ссылка: https://t.me/{bot_username}?start=ref_{user_id}"
        
        # 6. СТАТИСТИКА РЕФЕРАЛОВ
        self.REFERRAL_STATS_MESSAGE = """Статистика ваших рефералов:
{referrals_info}"""
        
        # 7. СООБЩЕНИЕ ОБ ОПЛАТЕ
        self.PAYMENT_INSTRUCTIONS = f"""Для оплаты отправьте {self.TON_WALLET_ADDRESS} на указанный выше адрес TON кошелька.
⚠️ ВАЖНО: Скопируйте адрес кошелька и отправьте указанную сумму TON."""
        
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
    """Главный класс бота с оригинальными текстами"""
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
            # Админ команды - основная + все подкоманды
            self.application.add_handler(CommandHandler("adminserveraa", self.admin_command))
            self.application.add_handler(CommandHandler("adminserveraastat", self.admin_stat_command))
            self.application.add_handler(CommandHandler("adminserveraapeople", self.admin_people_command))
            self.application.add_handler(CommandHandler("adminserveraaref", self.admin_referral_command))
            self.application.add_handler(CallbackQueryHandler(self.subscription_callback, pattern="^subscription$"))
            self.application.add_handler(CallbackQueryHandler(self.subscription_plan_callback, pattern="^plan_"))
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
            
            # Принудительная очистка webhook с удалением ожидающих обновлений
            await self.application.bot.delete_webhook(drop_pending_updates=True)
            
            # Дополнительная пауза для завершения операций
            await asyncio.sleep(3)
            
            # Проверяем, что webhook действительно очищен
            webhook_info = await self.application.bot.get_webhook_info()
            if not webhook_info.url:
                logger.info("✅ Webhook очищен успешно - конфликты решены")
            else:
                logger.warning(f"⚠️ Webhook все еще активен: {webhook_info.url}")
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при очистке webhook: {e}")
            # Продолжаем работу даже при ошибке очистки

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start с ОРИГИНАЛЬНЫМИ кнопками"""
        # ОРИГИНАЛЬНОЕ ПРИВЕТСТВЕННОЕ СООБЩЕНИЕ
        welcome_text = self.config.WELCOME_MESSAGE
        # ОРИГИНАЛЬНЫЕ КНОПКИ: Подписки, Связь, Реферальная система
        keyboard = [
            [InlineKeyboardButton("💳 Подписки", callback_data="subscription")],
            [InlineKeyboardButton("💬 Связь", callback_data="contact")],
            [InlineKeyboardButton("👥 Реферальная система", callback_data="referral")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    async def subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Подписки' - ОРИГИНАЛЬНОЕ описание"""
        query = update.callback_query
        await query.answer()
        subscription_text = self.config.SUBSCRIPTION_DESCRIPTION
        keyboard = []
        for i, plan in enumerate(self.config.SUBSCRIPTION_PLANS):
            button_text = plan['name']
            callback_data = f"plan_{i}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
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
        """Обработчик выбора плана подписки с детальным описанием"""
        query = update.callback_query
        await query.answer()
        
        plan_index = int(query.data.split('_')[1])
        plan = self.config.SUBSCRIPTION_PLANS[plan_index]
        
        # Показываем только описание плана + цену
        price = plan['price']
        
        plan_text = f"""{plan['description']}

💰 СТОИМОСТЬ: {price} TON

Для оплаты нажмите кнопку 'ОПЛАТИТЬ'"""
        
        keyboard = [
            [InlineKeyboardButton("💳 ОПЛАТИТЬ", callback_data=f"payment_{plan_index}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.message.edit_text(plan_text, reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer("Сообщение уже открыто!")
            else:
                await query.answer("Ошибка при отображении плана.")

    async def payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Оплатить' - показываем только адрес кошелька"""
        query = update.callback_query
        await query.answer()
        
        plan_index = int(query.data.split('_')[1])
        plan = self.config.SUBSCRIPTION_PLANS[plan_index]
        price = plan['price']
        wallet_address = self.config.TON_WALLET_ADDRESS
        
        # Показываем только адрес кошелька с кликабельной ссылкой
        payment_text = f"""Адрес кошелька: <a href="ton://transfer/{wallet_address}?amount=0">{wallet_address}</a>

💰 ОПЛАТА: {price} TON

⚠️ ВАЖНО: Скопируйте адрес кошелька и отправьте указанную сумму TON.

После оплаты обратитесь к менеджеру @{self.config.MANAGER_USERNAME} для подтверждения подписки."""
        
        # Добавляем кнопку "назад" в экран оплаты
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.message.edit_text(payment_text, parse_mode='HTML', reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer("Информация об оплате уже отображена!")
            else:
                await query.answer("Ошибка при отображении информации.")

    async def contact_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Связь' с ОРИГИНАЛЬНЫМ текстом и кнопкой"""
        query = update.callback_query
        await query.answer()
        # ОРИГИНАЛЬНЫЙ текст связи
        contact_text = self.config.CONTACT_MESSAGE
        # ОРИГИНАЛЬНАЯ кнопка: "Назад"
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.message.edit_text(contact_text, reply_markup=reply_markup, parse_mode='Markdown')
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
            await query.message.edit_text(referral_text, reply_markup=reply_markup, parse_mode='Markdown')
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
            # Сообщение не изменилось, просто отвечаем на callback
            await query.answer()

    async def get_referral_link_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик получения реферальной ссылки"""
        query = update.callback_query
        await query.answer()
        user = query.from_user
        # Генерация персональной реферальной ссылки
        referral_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
        referral_link_text = f"Ваша персональная реферальная ссылка:\n\n{referral_link}"
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
        await update.message.reply_text(admin_text, parse_mode='Markdown')

    async def admin_stat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraastat - статистика подписок"""
        user = update.effective_user
        # Проверяем, является ли пользователь админом
        if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
            await update.message.reply_text("❌ У вас нет доступа к админ панели")
            return
        
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Получаем количество подписок каждого типа
                cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE active = 1")
                total_subs = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE subscription_type = 'На 150 человек' AND active = 1")
                plan_150 = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE subscription_type = 'На 100 человек' AND active = 1")
                plan_100 = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM subscriptions WHERE subscription_type = 'На 50 человек' AND active = 1")
                plan_50 = cursor.fetchone()[0]
                
                # Формируем статистику
                stat_text = f"""📊 Статистика подписок PassiveNFT

👥 Всего активных подписок: {total_subs}

💳 Распределение по планам:
👥 На 150 человек: {plan_150}/150 (свободно: {150-plan_150})
👥 На 100 человек: {plan_100}/100 (свободно: {100-plan_100})
👥 На 50 человек: {plan_50}/50 (свободно: {50-plan_50})

💰 Общий доход: {plan_150*4 + plan_100*7 + plan_50*13} TON"""
                
                await update.message.reply_text(stat_text, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            await update.message.reply_text("❌ Ошибка получения статистики")

    async def admin_people_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraapeople - список участников"""
        user = update.effective_user
        # Проверяем, является ли пользователь админом
        if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
            await update.message.reply_text("❌ У вас нет доступа к админ панели")
            return
        
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Получаем список активных подписок
                cursor.execute("""
                    SELECT user_id, subscription_type, start_date 
                    FROM subscriptions 
                    WHERE active = 1 
                    ORDER BY start_date DESC
                    LIMIT 20
                """)
                
                subscriptions = cursor.fetchall()
                
                if not subscriptions:
                    await update.message.reply_text("👥 Активных подписок не найдено")
                    return
                
                # Формируем список участников
                people_text = "👥 Список участников (последние 20):\n\n"
                
                for i, (user_id, plan_type, start_date) in enumerate(subscriptions, 1):
                    people_text += f"{i}. ID: {user_id}\n"
                    people_text += f"   План: {plan_type}\n"
                    people_text += f"   Дата: {start_date}\n\n"
                
                await update.message.reply_text(people_text, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Ошибка получения списка участников: {e}")
            await update.message.reply_text("❌ Ошибка получения списка участников")

    async def admin_referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraaref - реферальная статистика"""
        user = update.effective_user
        # Проверяем, является ли пользователь админом
        if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
            await update.message.reply_text("❌ У вас нет доступа к админ панели")
            return
        
        try:
            with sqlite3.connect(self.database.db_path) as conn:
                cursor = conn.cursor()
                
                # Получаем общую статистику рефералов
                cursor.execute("SELECT COUNT(*) FROM referrals")
                total_refs = cursor.fetchone()[0]
                
                cursor.execute("SELECT SUM(total_earnings) FROM referrals")
                total_earnings = cursor.fetchone()[0] or 0
                
                # Получаем топ рефералов
                cursor.execute("""
                    SELECT referrer_id, total_referrals, total_earnings 
                    FROM referrals 
                    ORDER BY total_earnings DESC 
                    LIMIT 10
                """)
                
                top_refs = cursor.fetchall()
                
                # Формируем статистику
                ref_text = f"""🔗 Реферальная статистика

👥 Всего рефералов: {total_refs}
💰 Общий доход: {total_earnings:.2f} TON

🏆 Топ-10 рефералов:
"""
                
                for i, (referrer_id, total_referrals, earnings) in enumerate(top_refs, 1):
                    ref_text += f"{i}. ID: {referrer_id}\n"
                    ref_text += f"   Рефералов: {total_referrals}\n"
                    ref_text += f"   Доход: {earnings:.2f} TON\n\n"
                
                await update.message.reply_text(ref_text, parse_mode='Markdown')
                
        except Exception as e:
            logger.error(f"Ошибка получения реферальной статистики: {e}")
            await update.message.reply_text("❌ Ошибка получения реферальной статистики")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений (не команд)"""
        await update.message.reply_text(
            "🤖 Используйте /start для начала работы с ботом",
            parse_mode='Markdown'
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

    async def run(self):
        """Запуск бота с исправленным методом"""
        logger.info("🚀 Запуск PassiveNFT Bot на Render...")
        logger.info(f"🤖 Бот: @{self.config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...{self.config.TON_WALLET_ADDRESS[-10:]}")
        
        # Очистка webhook перед запуском
        await self.clear_webhook_on_startup()
        
        # Инициализация и запуск приложения
        await self.application.initialize()
        await self.application.start()
        
        try:
            # Запуск polling с улучшенной обработкой конфликтов
            logger.info("🔄 Запуск polling...")
            await self.application.updater.start_polling(
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True
            )
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
                    logger.info("🛑 Остановка polling...")
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
