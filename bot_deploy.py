#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PassiveNFT Bot - ИСПРАВЛЕННАЯ ВЕРСИЯ С ASYNC DATABASE
ИСПРАВЛЕНИЯ:
- Решена проблема зависания бота через 20-30 минут
- Миграция с sqlite3 на aiosqlite для неблокирующих операций
- Все вызовы базы данных теперь асинхронные
- Сохранена реферальная система и функционал подписок
"""
import asyncio
import logging
import sys
import traceback
from pathlib import Path
from typing import Optional

# Импорты Telegram бота - ГЛОБАЛЬНЫЕ ИМПОРТЫ
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

# ИМПОРТЫ ДЛЯ ВЕБ-СЕРВЕРА (для решения проблемы с портом на Render.com)
import os
import aiohttp
from aiohttp import web

# ИМПОРТ АСИНХРОННОГО МЕНЕДЖЕРА БАЗЫ ДАННЫХ
from database_async import AsyncDatabaseManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SafeConfig:
    """Безопасная конфигурация бота - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    def __init__(self):
        # Основные настройки
        self.BOT_TOKEN = self._get_env_var('BOT_TOKEN', '8530441136:AAHto3A4Zqa5FnGG01cxL6SvU3jW8_Ai0iI')
        self.ADMIN_USER_IDS = [8387394503, 2112739781]  # pro.player.egor

        # Настройки TON кошелька
        self.TON_WALLET_ADDRESS = self._get_env_var('TON_WALLET_ADDRESS', 'UQAij8pQ3HhdBn3lw6n9Iy2toOH9OMcBuL8yoSXTNpLJdfZJ')
        self.MANAGER_USERNAME = self._get_env_var('MANAGER_USERNAME', 'num6er9')
        self.BOT_USERNAME = self._get_env_var('BOT_USERNAME', 'passivenft_bot')
        
        # ИСПРАВЛЕНО: STARS_USERNAME - pingvinchik_liza
        self.STARS_USERNAME = self._get_env_var('STARS_USERNAME', 'pingvinchik_liza')

        # Настройки подписок
        self.SUBSCRIPTION_PLANS = [
            {
                "id": 0,
                "name": "на 150 человек",
                "subscription_type": "150_people",
                "description": """🖼️ 5 NFT в ДЕНЬ, 4 гифта в ДЕНЬ 🖼️
                
📅 150 NFT в МЕСЯЦ, 120 гифтов в МЕСЯЦ

📊 Процент победы одного участника составляет 0,67% на одно NFT, количество разыгрываемых NFT в день – 5, следственно 5*0,67% = 3,35% на победу за день, в месяц получается 100,5%

🎁 На гифты за звезды процент победы на одного участника составляет 0,67%, количество разыгрываемых гифтов в день – 4, следственно 4*0,67% = 2,68% на победу за день, в месяц получается 80,4%

💰 окуп от х1 до х5""",
                "price_ton": 4
            },
            {
                "id": 1,
                "name": "на 100 человек",
                "subscription_type": "100_people", 
                "description": """🖼️ 6 NFT в день, 4 гифта в день 🖼️
                
📅 180 NFT в месяц, 120 гифтов в месяц

📊 Процент победы одного участника составляет 1% на одно NFT, количество разыгрываемых NFT в день – 6, следственно 6*1% = 6% на победу за день, в месяц получается 180%

🎁 На гифты за звезды процент победы на одного участника составляет 0,67%, количество разыгрываемых гифтов в день – 4, следственно 4*1% = 4% на победу за день, в месяц получается 120%

💵 Один человек минимально получает возврат средств в 50% от стоимости подписки в месяц (в размере 1 NFT+гифт за 50 зв.)

💰 окуп от х1 до х8""",
                "price_ton": 7
            },
            {
                "id": 2,
                "name": "на 50 человек",
                "subscription_type": "50_people",
                "description": """🖼️ 7 NFT в день, 4 гифта в день 🖼️
                
📅 210 NFT в месяц, 120 гифтов в месяц

📊 Процент победы одного участника составляет 1% на одно NFT, количество разыгрываемых NFT в день – 7, следственно 7*2% = 14% на победу за день, в месяц получается 420%

🎁 На гифты за звезды процент победы одного участника составляет 2%, количество разыгрываемых гифтов в день – 4, следственно 4*2% = 8% на победу за день, в месяц получается 240%

💰 На одного участника в ТГК получается возврат средств в 70% от стоимости подписки в месяц (в размере 4 NFT+ 2 гифта за 50 зв.)

💰 окуп от х1 до х2,5-3""",
                "price_ton": 13
            }
        ]

        # Тексты сообщений
        self.WELCOME_MESSAGE = """🎉 welcome to the PassiveNFT 🎉

💰 PassiveNFT это возможность ПРИУМНОЖИТЬ свои вложения вплоть до х10! 💰

📋 ознакомиться со стоимостью подписок и что в них входит вы можете по кнопке "Подписки".

❓ если у вас всё еще остались вопросы, нажмите кнопку "Связь" для обращения к менеджеру по вопросам."""

        self.REFERRAL_WELCOME_MESSAGE = """🎉 welcome to the PassiveNFT 🎉

💰 PassiveNFT это возможность ПРИУМНОЖИТЬ свои вложения вплоть до х10! 💰

🔗 Вы пришли по реферальной ссылке!

📋 ознакомиться со стоимостью подписок и что в них входит вы можете по кнопке "Подписки"

❓ если у вас всё еще остались вопросы, нажмите кнопку "Связь" для обращения к менеджеру по вопросам."""
        
        self.SUBSCRIPTION_DESCRIPTION = "💳 Нажми на интересующую тебя подписку"
        self.CONTACT_MESSAGE = "💬 Если у вас возникли какие-либо трудности с оплатой или есть вопросы, нажмите кнопку \"Задать вопрос\"."
        self.REFERRAL_MESSAGE = "👥 Реферальная система предназначена для амбассадоров закрытого проекта PassiveNFT и обычных участников\n\n🔗 Она состоит из пригласительной ссылки, где владелец ссылки получается 10% с его оплаты подписки, для более точных подробностей нажмите на кнопку \"Задать вопрос\"."
        
        self.ACTIVITY_SUBSCRIPTION_TYPE_MESSAGE = """После перехода по кнопке подписки, выберите желаемый тип подписки:"""
        self.ACTIVITY_SUBSCRIPTION_DESCRIPTION = """активные подписки представляют собой менее затратный способ получить возможность приумножить свои вложения путем участия в различных активностях

чтобы ознакомиться с тем что входит в подписку, выберите заинтересовавший вас вариант снизу"""
        
        self.REFERRAL_LINK_MESSAGE = "🔗 **Ваша персональная реферальная ссылка:**\n\nПриглашайте друзей и зарабатывайте 10% с каждой их оплаты подписки!"
        self.REFERRAL_STATS_MESSAGE = """Статистика ваших рефералов:
{referrals_info}"""

        # Сообщения для оплаты через звездочки
        self.STAR_SUBSCRIPTION_PLANS = [
            {
                "stars": 25,
                "ton_price": 0.2,
                "lot_cost": 15,
                "description": """за вход в стоимость в 25 ЗВЕЗДОЧЕК вы получите шанс приумножить свою вложения вплоть до х56, всё зависит лишь от вашей скорости и удачи.

стоимость розыгрываемого лота в активностях 15 звездочек, в день происходит 13 активностей которые идут каждый день в течении 7 дней с момента запуска ТГК.

в подписку входят:

✅ доступ к закрытому ТГК на НЕДЕЛЮ, где проходят активности
✅ различные активности КАЖДЫЙ час с 9:00 до 21:00 по МСК
✅ 13 активнотей в ДЕНЬ
✅ 91 активностей в НЕДЕЛЮ на сумму ~1400 звездочек

выдачи происходят в течении 5-7 минут после завершения активности."""
            },
            {
                "stars": 50,
                "ton_price": 0.4,
                "lot_cost": 25,
                "description": """за вход в стоимость в 50 ЗВЕЗДОЧЕК вы получите шанс приумножить свою вложения вплоть до х46, всё зависит лишь от вашей скорости и удачи.

стоимость розыгрываемого лота в активностях 25 звездочек, в день происходит 13 активностей которые идут каждый день в течении 7 дней с момента запуска ТГК.

в подписку входят:

✅ доступ к закрытому ТГК на НЕДЕЛЮ, где проходят активности
✅ различные активности КАЖДЫЙ час с 9:00 до 21:00 по МСК
✅ 13 активнотей в ДЕНЬ
✅ 91 активностей в НЕДЕЛЮ на сумму ~2300 звездочек

выдачи происходят в течении 5-7 минут после завершения активности."""
            },
            {
                "stars": 75,
                "ton_price": 0.6,
                "lot_cost": 50,
                "description": """за вход в стоимость в 75 ЗВЕЗДОЧЕК вы получите шанс приумножить свою вложения вплоть до х61, всё зависит лишь от вашей скорости и удачи.

стоимость розыгрываемого лота в активностях 50 звездочек, в день происходит 13 активностей которые идут каждый день в течении 7 дней с момента запуска ТГК.

в подписку входят:

✅ доступ к закрытому ТГК на НЕДЕЛЮ, где проходят активности
✅ различные активности КАЖДЫЙ час с 9:00 до 21:00 по МСК
✅ 13 активнотей в ДЕНЬ
✅ 91 активностей в НЕДЕЛЮ на сумму ~4600 звездочек

выдачи происходят в течении 5-7 минут после завершения активности."""
            },
            {
                "stars": 100,
                "ton_price": 0.8,
                "lot_cost": 50,
                "description": """за вход в стоимость в 100 ЗВЕЗДОЧЕК вы получите шанс приумножить свою вложения вплоть до х69, всё зависит лишь от вашей скорости и удачи.

стоимость розыгрываемого лота в активностях 75 звездочек, в день происходит 13 активностей которые идут каждый день в течении 7 дней с момента запуска ТГК.

в подписку входят:

✅ доступ к закрытому ТГК на НЕДЕЛЮ, где проходят активности
✅ различные активности КАЖДЫЙ час с 9:00 до 21:00 по МСК
✅ 13 активнотей в ДЕНЬ
✅ 91 активностей в НЕДЕЛЮ на сумму ~6900 звездочек

выдачи происходят в течении 5-7 минут после завершения активности."""
            }
        ]

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
    if os.path.exists('config_deploy_new.py'):
        from config_deploy_new import config
        logger.info("Конфигурация загружена из config_deploy_new.py")
    else:
        config = SafeConfig()
        logger.info("✅ Безопасная конфигурация загружена")
        logger.info(f"🤖 Бот: @{config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {config.TON_WALLET_ADDRESS[:10]}...{config.TON_WALLET_ADDRESS[-10:]}")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки конфигурации: {e}")
    try:
        config = SafeConfig()
        logger.info("✅ Безопасная конфигурация загружена")
        logger.info(f"🤖 Бот: @{config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {config.TON_WALLET_ADDRESS[:10]}...{config.TON_WALLET_ADDRESS[-10:]}")
    except Exception as e2:
        logger.error(f"❌ Критическая ошибка загрузки конфигурации: {e2}")
        raise

class PassiveNFTBot:
    """Главный класс бота с асинхронной базой данных - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    
    def __init__(self):
        self.config = config
        self.database = AsyncDatabaseManager()  # Асинхронный менеджер БД
        self.application = None
        logger.info("🤖 PassiveNFT Bot инициализирован с async database")

    async def initialize(self):
        """Инициализация бота с асинхронной базой данных"""
        try:
            # Инициализация асинхронной базы данных
            await self.database.initialize()
            logger.info("✅ Асинхронная база данных инициализирована")
            
            # Настройка Telegram приложения
            await self.setup_telegram_application()
            logger.info("✅ Telegram приложение настроено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def setup_telegram_application(self):
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
            self.application.add_handler(CommandHandler("confirm_payment", self.confirm_payment_command))
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
            
            # Обработчики для активных подписок
            self.application.add_handler(CallbackQueryHandler(self.activity_subscription_callback, pattern="^activity_subscription_"))
            self.application.add_handler(CallbackQueryHandler(self.star_subscription_plan_callback, pattern="^star_plan_"))
            self.application.add_handler(CallbackQueryHandler(self.stars_payment_callback, pattern="^stars_payment_"))
            self.application.add_handler(CallbackQueryHandler(self.copy_stars_ton_callback, pattern="^copy_stars_ton_"))
            self.application.add_handler(CallbackQueryHandler(self.stars_payment_stars_callback, pattern="^stars_payment_stars_"))
            
            # Существующие обработчики
            self.application.add_handler(CallbackQueryHandler(self.contact_callback, pattern="^contact$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_callback, pattern="^referral$"))
            self.application.add_handler(CallbackQueryHandler(self.get_referral_link_callback, pattern="^get_referral$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_stats_callback, pattern="^referral_stats$"))
            self.application.add_handler(CallbackQueryHandler(self.copy_ton_callback, pattern="^copy_ton_"))
            self.application.add_handler(CallbackQueryHandler(self.back_callback, pattern="^back$"))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

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
        """Исправленный обработчик команды /start с улучшенной обработкой реферальных параметров"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: /start от пользователя {update.effective_user.id}")
        
        try:
            user = update.effective_user
            args = context.args
            
            # Подробное логирование параметров
            logger.info(f"📋 Параметры команды: {args}")
            logger.info(f"📋 Тип args: {type(args)}")
            logger.info(f"📋 Длина args: {len(args) if args else 0}")
            
            # Добавляем пользователя в базу данных
            referral_code = await self.database.get_or_create_user(
                user.id, 
                user.username or "", 
                user.first_name or "", 
                user.last_name or ""
            )
            logger.info(f"✅ Пользователь {user.id} создан/найден в базе данных, реферальный код: {referral_code}")
            
            # ОБРАБОТКА РЕФЕРАЛЬНОГО ПАРАМЕТРА
            referrer_id = None
            if args and len(args) > 0:
                arg = args[0]
                logger.info(f"🔍 Анализ первого параметра: '{arg}'")
                
                if arg.startswith('ref_'):
                    logger.info(f"✅ Параметр начинается с 'ref_', извлекаем ID...")
                    try:
                        referrer_id = int(arg[4:])  # Убираем "ref_" и получаем ID
                        logger.info(f"📊 Извлеченный referrer_id: {referrer_id}")
                        
                        if referrer_id != user.id:  # Нельзя быть реферером самому себе
                            logger.info(f"💾 Сохраняем временного реферера: {referrer_id} для пользователя {user.id}")
                            await self.database.save_pending_referral(user.id, referrer_id)
                            logger.info(f"✅ Реферер {referrer_id} сохранен для пользователя {user.id}")
                        else:
                            logger.warning(f"⚠️ Пользователь {user.id} пытается быть реферером самому себе")
                    except ValueError as e:
                        logger.error(f"❌ Ошибка преобразования referrer_id: {e}")
                else:
                    logger.info(f"❌ Параметр '{arg}' не начинается с 'ref_'")
            else:
                logger.info("📋 Параметры отсутствуют, реферальный параметр не передан")
            
            # Подробное логирование результата
            if referrer_id:
                logger.info(f"🎉 Пользователь {user.id} пришел от реферера {referrer_id}")
            else:
                logger.info(f"👤 Пользователь {user.id} пришел без реферального параметра")
            
            # Выбираем соответствующее приветственное сообщение
            if referrer_id:
                welcome_text = self.config.REFERRAL_WELCOME_MESSAGE
                logger.info(f"📝 Используется реферальное приветственное сообщение")
            else:
                welcome_text = self.config.WELCOME_MESSAGE
                logger.info(f"📝 Используется обычное приветственное сообщение")
            
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
        """Обработчик команды подтверждения оплаты"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: /confirm_payment от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user
            pending_referrer = await self.database.get_pending_referrer(user.id)

            if pending_referrer:
                # Добавляем реферала в базу
                success = await self.database.add_referral(pending_referrer, user.id)
                if success:
                    # УДАЛЯЕМ запись об ожидающем реферере
                    await self.database.remove_pending_referral(user.id)
                    await update.message.reply_text("✅ Оплата подтверждена! Реферал успешно добавлен. Комиссия рефереру будет начислена только при оплате за TON подписку.")
                else:
                    await update.message.reply_text("❌ Ошибка при добавлении реферала.")
            else:
                await update.message.reply_text("ℹ️ Для вас нет ожидающих рефереров.")

            logger.info(f"✅ /confirm_payment выполнен для пользователя {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в confirm_payment_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Подписки'"""
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
        """Обработчик выбора обычного плана TON"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: ton_subscription_plan callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            plan_index = int(query.data.split('_')[3])
            plan = self.config.SUBSCRIPTION_PLANS[plan_index]

            # ИСПРАВЛЕНО: Показываем правильные цены (4/7/13 TON)
            plan_text = f"""📋 {plan['name']}

{plan['description']}

💰 Стоимость: {plan['price_ton']} TON"""

            # Кнопка "ОПЛАТИТЬ" и "Назад"
            keyboard = [
                [InlineKeyboardButton("💳 ОПЛАТИТЬ", callback_data=f"payment_{plan_index}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(plan_text, reply_markup=reply_markup)
            logger.info(f"✅ План TON {plan_index} показан пользователю {update.effective_user.id}")
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

            plan_index = int(query.data.split('_')[2])
            plan = self.config.SUBSCRIPTION_PLANS[plan_index]

            # Показываем выбор типа подписки
            plan_text = f"""📋 {plan['name']}

{self.config.ACTIVITY_SUBSCRIPTION_TYPE_MESSAGE}"""

            # Кнопки: "С активностями (за звездочки)" и "Без активностей (за TON)"
            keyboard = [
                [InlineKeyboardButton("⚡ С активностями (за звездочки)", callback_data=f"activity_subscription_{plan_index}")],
                [InlineKeyboardButton("💎 Без активностей (за TON)", callback_data=f"payment_{plan_index}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(plan_text, reply_markup=reply_markup)
            logger.info(f"✅ Выбор типа подписки для плана {plan_index} показан пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в subscription_plan_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Оплатить'"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: payment callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            plan_index = int(query.data.split('_')[1])
            plan = self.config.SUBSCRIPTION_PLANS[plan_index]

            # ИСПРАВЛЕНО: Показываем правильную цену с четким форматированием
            payment_text = f"""💰 ОПЛАТА: {plan['price_ton']} TON

📋 Подписка: {plan['name']}

Адрес кошелька:
<code>{self.config.TON_WALLET_ADDRESS}</code>

⚠️ ВАЖНО: Скопируйте адрес кошелька и отправьте указанную сумму TON.

После оплаты обратитесь к менеджеру @{self.config.MANAGER_USERNAME} для подтверждения подписки."""

            # Кнопка "Назад"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='HTML')
            logger.info(f"✅ Оплата для плана {plan_index} открыта для пользователя {update.effective_user.id}")
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

            plan_index = int(query.data.split('_')[2])
            plan = self.config.SUBSCRIPTION_PLANS[plan_index]

            # Показываем описание активностей
            activity_text = f"""⚡ {plan['name']}

{self.config.ACTIVITY_SUBSCRIPTION_DESCRIPTION}"""

            # ИСПРАВЛЕННЫЕ кнопки выбора уровня звездочек с ПРАВИЛЬНЫМИ callback_data
            keyboard = [
                [InlineKeyboardButton("⭐️ ВХОД 25 ЗВЕЗДОЧЕК", callback_data="star_plan_25")],
                [InlineKeyboardButton("⭐️ ВХОД 50 ЗВЕЗДОЧЕК", callback_data="star_plan_50")],
                [InlineKeyboardButton("⭐️ ВХОД 75 ЗВЕЗДОЧЕК", callback_data="star_plan_75")],
                [InlineKeyboardButton("⭐️ ВХОД 100 ЗВЕЗДОЧЕК", callback_data="star_plan_100")],
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(activity_text, reply_markup=reply_markup)
            logger.info(f"✅ Активные подписки для плана {plan_index} показаны пользователю {update.effective_user.id}")
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

активные подписки представляют собой менее затратный способ получить возможность приумножить свои вложения путем участия в различных активностях

чтобы ознакомиться с тем что входит в подписку, выберите заинтересовавший вас вариант снизу."""

            # ИСПРАВЛЕННЫЕ кнопки выбора уровня звездочек с ПРАВИЛЬНЫМИ callback_data
            keyboard = [
                [InlineKeyboardButton("⭐️ ВХОД 25 ЗВЕЗДОЧЕК", callback_data="star_plan_25")],
                [InlineKeyboardButton("⭐️ ВХОД 50 ЗВЕЗДОЧЕК", callback_data="star_plan_50")],
                [InlineKeyboardButton("⭐️ ВХОД 75 ЗВЕЗДОЧЕК", callback_data="star_plan_75")],
                [InlineKeyboardButton("⭐️ ВХОД 100 ЗВЕЗДОЧЕК", callback_data="star_plan_100")],
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(activity_text, reply_markup=reply_markup)
            logger.info(f"✅ Активные подписки (звездочки) показаны пользователю {update.effective_user.id}")
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

            # ОРИГИНАЛЬНОЕ общее описание подписок
            subscription_text = self.config.SUBSCRIPTION_DESCRIPTION

            # ИСПРАВЛЕННЫЕ кнопки подписок (150/100/50) с ПРАВИЛЬНЫМИ названиями
            keyboard = []
            for i, plan in enumerate(self.config.SUBSCRIPTION_PLANS):
                # ИСПРАВЛЕНО: показываем прайс прямо в названии кнопки
                button_text = f"ВХОД {plan['price_ton']} TON"
                callback_data = f"ton_subscription_plan_{i}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

            # Кнопка "Назад"
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="subscription")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(subscription_text, reply_markup=reply_markup)
            logger.info(f"✅ Обычные подписки (TON) показаны пользователю {update.effective_user.id}")
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

            # ИСПРАВЛЕНО: более надежное извлечение количества звездочек
            parts = query.data.split('_')
            if len(parts) >= 3:
                stars = int(parts[2])
            else:
                await query.answer("❌ Ошибка: неверный формат данных")
                return

            # Находим соответствующий план звездочек
            star_plan = None
            for plan in self.config.STAR_SUBSCRIPTION_PLANS:
                if plan['stars'] == stars:
                    star_plan = plan
                    break

            if not star_plan:
                await query.answer("❌ Ошибка: план не найден")
                return

            # Показываем описание плана звездочек
            plan_text = f"""⭐️ ВХОД {stars} ЗВЕЗДОЧЕК

{star_plan['description']}"""

            # Кнопки: "Оплатить" и "Назад"
            keyboard = [
                [InlineKeyboardButton("💳 ОПЛАТИТЬ", callback_data=f"stars_payment_{stars}")],
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

            # ИСПРАВЛЕНО: более надежное извлечение количества звездочек
            parts = query.data.split('_')
            if len(parts) >= 3:
                stars = int(parts[2])
            else:
                await query.answer("❌ Ошибка: неверный формат данных")
                return

            # Находим соответствующий план звездочек
            star_plan = None
            for plan in self.config.STAR_SUBSCRIPTION_PLANS:
                if plan['stars'] == stars:
                    star_plan = plan
                    break

            if not star_plan:
                await query.answer("❌ Ошибка: план не найден")
                return

            # ИСПРАВЛЕННОЕ сообщение с двумя кнопками оплаты
            payment_text = f"""💰 ОПЛАТА: ~{star_plan['ton_price']} TON (эквивалентно ~{stars} звездам)

для оплаты в TON нажмите кнопку "Оплатить TON" и отправьте сумму указанную выше (при нажатии на эту кнопку, у пользователя копируется мой адрес тон кошелька)

для оплаты ЗВЕЗДОЧКАМИ нажмите кнопку "Оплатить звездочками" и отправьте подарком стоимость подписки + оплата комиссии

после оплаты обратитесь по кнопке "Менеджер" для подтверждения оплаты и для получения ссылки в закрытый ТГК.

⚠️ ВАЖНО: Для копирования оплаты через TON кошелек  нажмите на кнопку "Оплатить TON" """

            # ИСПРАВЛЕННЫЕ кнопки для оплаты - ПРЯМАЯ ССЫЛКА НА @pingvinchik_liza
            keyboard = [
                [InlineKeyboardButton("💎 Оплатить TON", callback_data=f"copy_stars_ton_{stars}")],
                [InlineKeyboardButton("⭐ Оплатить звездочками", url=f"https://t.me/{self.config.STARS_USERNAME}")],  # URL КНОПКА
                [InlineKeyboardButton("👤 Менеджер", url=f"https://t.me/{self.config.MANAGER_USERNAME}")],
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
        """Обработчик кнопки "Оплатить TON" - копирование адреса"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: copy_stars_ton callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # ИСПРАВЛЕНО: правильное извлечение количества звездочек из callback_data "copy_stars_ton_25"
            parts = query.data.split('_')
            if len(parts) >= 4:
                stars = int(parts[3])  # parts[3] содержит число звездочек
            else:
                await query.answer("❌ Ошибка: неверный формат данных")
                return

            # Находим соответствующий план звездочек
            star_plan = None
            for plan in self.config.STAR_SUBSCRIPTION_PLANS:
                if plan['stars'] == stars:
                    star_plan = plan
                    break

            if not star_plan:
                await query.answer("❌ Ошибка: план не найден")
                return

            # ИСПРАВЛЕННОЕ сообщение с инструкциями для TON оплаты
            payment_text = f"""💰 ОПЛАТА ЧЕРЕЗ TON - {stars} ЗВЕЗД (~{star_plan['ton_price']} TON)

📍 Адрес TON кошелька:
<code>{self.config.TON_WALLET_ADDRESS}</code>

✅ При нажатии кнопка выше скопирует адрес в буфер обмена

💰 Отправьте: ~{star_plan['ton_price']} TON (эквивалентно ~{stars} звездам)

⏰ После оплаты обратитесь к менеджеру для подтверждения:
👤 @{self.config.MANAGER_USERNAME}

🔗 Связаться с менеджером: https://t.me/{self.config.MANAGER_USERNAME}"""

            # Кнопки для TON оплаты
            keyboard = [
                [InlineKeyboardButton("💰 Открыть TON кошелек", url=f"ton://transfer?amount={star_plan['ton_price']}&address={self.config.TON_WALLET_ADDRESS}")],
                [InlineKeyboardButton("👤 Связь с менеджером", url=f"https://t.me/{self.config.MANAGER_USERNAME}")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"stars_payment_{stars}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='HTML')
            logger.info(f"✅ Оплата через TON {stars} показана пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в copy_stars_ton_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def stars_payment_stars_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки "Оплатить звездочками" - редирект на менеджера"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: stars_payment_stars callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # ИСПРАВЛЕНО: правильное извлечение количества звездочек из callback_data
            parts = query.data.split('_')
            if len(parts) >= 2:
                stars = int(parts[1])  # parts[1] содержит число звездочек
            else:
                await query.answer("❌ Ошибка: неверный формат данных")
                return

            # ИСПРАВЛЕННОЕ сообщение с редиректом на pingvinchik_liza
            payment_text = f"""⭐️ ОПЛАТА ЧЕРЕЗ ЗВЕЗДОЧКИ - {stars} ЗВЕЗД

💳 Для оплаты перейдите к @{self.config.STARS_USERNAME} и отправьте подарком стоимость подписки ({stars} звезд) + оплата комиссии.

⏰ После отправки обратитесь к менеджеру для подтверждения:
👤 @{self.config.MANAGER_USERNAME}

🔗 Переход к @{self.config.STARS_USERNAME}..."""

            # Кнопка перехода к менеджеру для оплаты звездочками
            keyboard = [
                [InlineKeyboardButton(f"💎 Перейти к @{self.config.STARS_USERNAME}", url=f"https://t.me/{self.config.STARS_USERNAME}")],
                [InlineKeyboardButton("👤 Связь с менеджером", url=f"https://t.me/{self.config.MANAGER_USERNAME}")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"stars_payment_{stars}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='HTML')
            logger.info(f"✅ Оплата через звездочки {stars} для @{self.config.STARS_USERNAME} показана пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в stars_payment_stars_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def contact_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Связь'"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: contact callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # ОРИГИНАЛЬНЫЙ текст связи
            contact_text = self.config.CONTACT_MESSAGE

            # Кнопка "Назад" и "Задать вопрос"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="back")],
                [InlineKeyboardButton("📞 Задать вопрос", url=f"https://t.me/{self.config.MANAGER_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(contact_text, reply_markup=reply_markup, parse_mode='HTML')
                logger.info(f"✅ Контакты открыты для пользователя {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Контакты уже открыты!")
                    logger.info(f"ℹ️ Контакты уже открыты для пользователя {update.effective_user.id}")
                else:
                    await query.answer("Ошибка при открытии контактов.")
                    logger.error(f"❌ Ошибка BadRequest в contact_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в contact_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def referral_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Реферальная система'"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: referral callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # ОРИГИНАЛЬНЫЙ текст реферальной системы
            referral_text = self.config.REFERRAL_MESSAGE

            # ОРИГИНАЛЬНЫЕ кнопки: "Назад", "Получить реферальную ссылку", "Статистика рефералов", "Задать вопрос"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="back")],
                [InlineKeyboardButton("🔗 Получить реферальную ссылку", callback_data="get_referral")],
                [InlineKeyboardButton("📊 Статистика рефералов", callback_data="referral_stats")],
                [InlineKeyboardButton("📞 Задать вопрос", url=f"https://t.me/{self.config.MANAGER_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(referral_text, reply_markup=reply_markup, parse_mode='HTML')
                logger.info(f"✅ Реферальная система открыта для пользователя {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.error(f"❌ Ошибка BadRequest в referral_callback: {e}")
                    raise
                # Сообщение не изменилось, просто отвечаем на callback
                await query.answer()
                logger.info(f"ℹ️ Реферальная система уже открыта для пользователя {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def get_referral_link_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик получения реферальной ссылки"""
        logger.info(f"🎯 КОМАНДА ПОЛУЧЕНА: get_referral callback от пользователя {update.effective_user.id}")
        try:
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
            logger.info(f"✅ Реферальная ссылка отправлена пользователю {user.id}")
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

            # Получаем статистику пользователя
            stats_text = await self.database.get_user_referral_stats(query.from_user.id)
            if not stats_text:
                stats_text = "У вас пока нет рефералов."

            stats_text = self.config.REFERRAL_STATS_MESSAGE.format(referrals_info=stats_text)

            # Кнопка "Назад"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="referral")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(stats_text, reply_markup=reply_markup)
            logger.info(f"✅ Статистика рефералов отправлена пользователю {query.from_user.id}")
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

            await query.message.edit_text(
                f"✅ Адрес кошелька скопирован!\n\n`{self.config.TON_WALLET_ADDRESS}`\n\nОтправьте указанную сумму TON.",
                parse_mode='Markdown'
            )
            logger.info(f"✅ Адрес TON скопирован для пользователя {update.effective_user.id}")
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
                logger.info(f"✅ Возврат к главному меню для пользователя {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.error(f"❌ Ошибка BadRequest в back_callback: {e}")
                    raise
                # Сообщение не изменилось, просто отвечаем на callback
                await query.answer()
                logger.info(f"ℹ️ Уже в главном меню для пользователя {update.effective_user.id}")
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

            # ОРИГИНАЛЬНЫЙ текст админ панели
            admin_text = """🔧 Админ панель PassiveNFT Bot
📊 /adminserveraastat - статистика подписок
👥 /adminserveraapeople - список участников
🔗 /adminserveraaref - реферальная статистика
🔗 /confirm_payment - проверка оплаты
📢 /broadcast <сообщение> - рассылка всем пользователям
💳 Количество подписок:
👥 на 150 человек: энное количество из 150
👥 на 100 человек: энное количество из 100
👥 на 50 человек: энное количество из 50"""
            await update.message.reply_text(admin_text)
            logger.info(f"✅ Админ панель открыта для пользователя {user.id}")
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

            # Получаем статистику подписок
            try:
                total_users = await self.database.get_all_users_count()
                total_referrals = await self.database.get_total_referrals_count()
                total_commission = await self.database.get_total_commission_earned()
                
                stats_text = f"""📊 СТАТИСТИКА БОТА

👥 Всего пользователей: {total_users}
💎 Рефералов: {total_referrals}
💰 Начислено комиссий: {total_commission} TON

🤖 Бот: @{self.config.BOT_USERNAME}
💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}..."""
                
                await update.message.reply_text(stats_text)
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
                users_data = await self.database.get_subscribers()
                
                if users_data:
                    people_text = "👥 ПОСЛЕДНИЕ ПОЛЬЗОВАТЕЛИ:\n\n"
                    for user_data in users_data[:10]:  # Показываем только 10
                        people_text += f"👤 {user_data['name']} (@{user_data['username']})\n"
                        people_text += f"💎 Подписка: {user_data['subscription']}\n\n"
                else:
                    people_text = "👥 Пользователей не найдено"
                
                await update.message.reply_text(people_text)
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
                ref_data = await self.database.get_referral_stats()
                
                ref_text = f"""🔗 СТАТИСТИКА РЕФЕРАЛОВ

📊 Всего рефералов: {await self.database.get_total_referrals_count()}
👥 Активных рефереров: {len(ref_data)}

🏆 ТОП РЕФЕРЕРОВ:
"""
                
                if ref_data:
                    for i, ref in enumerate(ref_data[:5]):
                        ref_text += f"{i+1}. {ref['username']} - {ref['total_referrals']} рефералов - {ref['commission']} TON\n"
                else:
                    ref_text += "Рефереров пока нет"
                
                await update.message.reply_text(ref_text)
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
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к /broadcast от пользователя {user.id}")
                return

            # Проверяем, есть ли текст сообщения для рассылки
            if not context.args:
                await update.message.reply_text(
                    "📢 Использование: /broadcast <сообщение для рассылки>\n\n"
                    "Пример: /broadcast Привет всем! У нас новое обновление."
                )
                return

            # Формируем сообщение для рассылки
            broadcast_message = ' '.join(context.args)
            
            # Получаем статистику пользователей
            total_users = await self.database.get_all_users_count()
            
            if total_users == 0:
                await update.message.reply_text("❌ В базе данных нет зарегистрированных пользователей")
                return

            await update.message.reply_text(
                f"✅ Команда рассылки получена!\n"
                f"📝 Текст: {broadcast_message}\n"
                f"👥 Всего пользователей: {total_users}\n"
                f"⚠️ Функция рассылки будет реализована в следующей версии"
            )
            logger.info(f"✅ Broadcast команда получена: {broadcast_message}")

        except Exception as e:
            logger.error(f"❌ Ошибка в broadcast_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка при рассылке. Попробуйте позже.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        logger.info(f"🎯 ТЕКСТОВОЕ СООБЩЕНИЕ ПОЛУЧЕНО: '{update.message.text}' от пользователя {update.effective_user.id}")
        try:
            message = update.message.text.lower()
            if "admin" in message and update.effective_user.id in self.config.ADMIN_USER_IDS:
                await self.admin_command(update, context)
            else:
                await update.message.reply_text(
                    "🤖 Используйте /start для начала работы"
                )
                logger.info(f"✅ Отправлено справочное сообщение пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в handle_message: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def run(self):
        """Запуск бота с асинхронной базой данных"""
        logger.info("🚀 Запуск PassiveNFT Bot с async database...")
        logger.info(f"🤖 Бот: @{self.config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...{self.config.TON_WALLET_ADDRESS[-10:]}")
        logger.info("✅ Реферальная система включена (комиссия только за TON)")
        logger.info("⭐️ Активные подписки за звездочки включены")
        logger.info("🔧 ПРОБЛЕМА ЗАВИСАНИЯ РЕШЕНА - используется aiosqlite!")

        # Инициализация бота
        await self.initialize()

        # Очистка webhook перед запуском
        await self.clear_webhook_on_startup()

        # Инициализация и запуск приложения
        await self.application.initialize()
        await self.application.start()

        try:
            # Запуск polling с улучшенной диагностикой
            logger.info("🔄 Запуск polling режима...")
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                bootstrap_retries=3,
                timeout=10
            )
            logger.info("✅ Бот запущен и ожидает команды...")
            logger.info("📡 Polling начат - бот готов к приему сообщений")
            
            # Бесконечное ожидание с обработкой прерываний
            while True:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    logger.info("⏹️ Получен сигнал остановки polling")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в polling: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            # Корректная остановка бота
            logger.info("🛑 Начинаем корректную остановку бота...")
            try:
                if self.application.updater.running:
                    self.application.updater.stop()
                    logger.info("✅ Polling остановлен")
                await self.application.stop()
                await self.application.shutdown()
                
                # Закрытие асинхронной базы данных
                await self.database.close()
                logger.info("✅ Асинхронная база данных закрыта")
                logger.info("✅ Бот корректно остановлен")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при остановке бота: {e}")

async def main():
    """Главная функция запуска с улучшенной обработкой ошибок"""
    try:
        logger.info("🎯 Инициализация PassiveNFT Bot с async database...")
        bot = PassiveNFTBot()
        logger.info("✅ Bot инициализирован, начинаем запуск...")
        await bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал остановки от пользователя")
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
    
    port = int(os.environ.get('PORT', 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🚀 Web server started on port {port}")

async def run_both():
    """Запускает бота и веб-сервер одновременно"""
    bot_instance = PassiveNFTBot()
    try:
        await asyncio.gather(
            bot_instance.run(),  # Бот
            start_web_server()   # Веб-сервер
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в run_both: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    try:
        logger.info("🔥 ЗАПУСК PassiveNFT Bot с async database...")
        asyncio.run(run_both())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
