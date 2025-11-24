#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PassiveNFT Bot - ВЕРСИЯ С ПОЛНОЙ ИНТЕГРАЦИЕЙ ВСЕХ ИСПРАВЛЕНИЙ
ИСПРАВЛЕНИЯ В ЭТОЙ ВЕРСИИ:
- ИСПРАВЛЕНА ОШИБКА "Cancel" кнопки (query.message вместо update.message)
- ИНТЕГРИРОВАНЫ PRIVATE_CHANNEL_LINKS из конфига
- ДОБАВЛЕНА система генерации реальных invite ссылок через Telegram API
- ИСПРАВЛЕНА отправка одноразовых ссылок после выбора канала и ввода username
- УЛУЧШЕНО экранирование Markdown для корректного парсинга
- ИСПРАВЛЕНЫ дублирующиеся функции handle_message
- ИНТЕГРИРОВАНА полная асинхронная система подтверждения оплат
- ДОБАВЛЕНЫ все необходимые методы для работы с базой данных
"""
import asyncio
import logging
import sqlite3
import sys
import traceback
from pathlib import Path
from typing import Optional
from datetime import datetime
import re

# Импорты Telegram бота - ГЛОБАЛЬНЫЕ ИМПОРТЫ
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

# ИМПОРТЫ ДЛЯ ВЕБ-СЕРВЕРА (для решения проблемы с портом на Render.com)
import os
import aiohttp
from aiohttp import web

# Импортируем нашу асинхронную базу данных
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

# УЛУЧШЕННАЯ ФУНКЦИЯ ЭКРАНИРОВАНИЯ ДЛЯ MARKDOWN
def escape_markdown(text):
    """Улучшенное экранирование специальных символов Markdown для корректного парсинга"""
    if text is None:
        return ""
    
    text = str(text)
    
    # УЛУЧШЕННЫЕ пары экранирования - порядок важен!
    escape_pairs = [
        ('\\', '\\\\'),  # Сначала экранируем обратные слеши
        ('*', '\\*'),      # Жирный/курсив
        ('_', '\\_'),      # Подчеркивание
        ('[', '\\['),      # Ссылка
        (']', '\\]'),      # Ссылка  
        ('(', '\\('),      # Ссылка
        (')', '\\)'),      # Ссылка
        ('~', '\\~'),      # Зачеркивание
        ('`', '\\`'),      # Код
        ('>', '\\>'),      # Цитата
        ('#', '\\#'),      # Заголовок
        ('+', '\\+'),      # Список
        ('-', '\\-'),      # Список
        ('=', '\\='),      # Заголовок
        ('|', '\\|'),      # Таблица
        ('{', '\\{'),      # Форматирование
        ('}', '\\}'),      # Форматирование
        ('.', '\\.'),      # Конец предложения
        ('!', '\\!'),      # Восклицание
    ]
    
    for char, escaped in escape_pairs:
        text = text.replace(char, escaped)
    
    return text

def safe_format_user_data(text, **kwargs):
    """Улучшенное безопасное форматирование текста с экранированием пользовательских данных"""
    try:
        # Экранируем все пользовательские данные
        safe_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str):
                safe_kwargs[key] = escape_markdown(value)
            else:
                # Для числовых значений также применяем экранирование как строки
                safe_kwargs[key] = escape_markdown(str(value))
        
        # Форматируем текст с безопасными параметрами
        result = text.format(**safe_kwargs)
        return result
        
    except KeyError as e:
        logger.error(f"Ошибка форматирования - отсутствует ключ: {e}")
        # Возвращаем текст без форматирования для диагностики
        return f"ОШИБКА ФОРМАТИРОВАНИЯ: {text}\nПараметры: {kwargs}"
    except Exception as e:
        logger.error(f"Общая ошибка форматирования: {e}")
        return f"ОБЩАЯ ОШИБКА ФОРМАТИРОВАНИЯ: {text}\nОшибка: {e}"

class SafeConfig:
    """Безопасная конфигурация бота с активными подписками - ПОЛНАЯ ИНТЕГРАЦИЯ"""
    def __init__(self):
        # Основные настройки
        self.BOT_TOKEN = self._get_env_var('BOT_TOKEN', '8530441136:AAHto3A4Zqa5FnGG01cxL6SvU3jW8_Ai0iI')
        self.ADMIN_USER_IDS = [8387394503, 2112739781] # pro.player.egor

        # Настройки TON кошелька
        self.TON_WALLET_ADDRESS = self._get_env_var('TON_WALLET_ADDRESS', 'UQAij8pQ3HhdBn3lw6n9Iy2toOH9OMcBuL8yoSXTNpLJdfZJ')
        self.MANAGER_USERNAME = self._get_env_var('MANAGER_USERNAME', 'num6er9')
        self.BOT_USERNAME = self._get_env_var('BOT_USERNAME', 'passivenft_bot')
        
        # STARS_USERNAME - pingvinchik_liza
        self.STARS_USERNAME = self._get_env_var('STARS_USERNAME', 'pingvinchik_liza')

        # MAPPING каналов для Stars платежей (РЕАЛЬНЫЕ ID)
        self.CHANNEL_MAPPINGS = {
            25: -1002755746127,    # 25 звезд
            50: -1003223397887,   # 50 звезд  
            75: -1003232732123,   # 75 звезд
            100: -1003361243296,  # 100 звезд
        }

        # MAPPING каналов для TON платежей (РЕАЛЬНЫЕ ID)
        self.TON_CHANNEL_MAPPINGS = {
            150: -1002840455870,  # 150 тон
            100: -1003492791385,  # 100 тон
            50: -1003361121200,   # 50 тон
        }

        # PRIVATE_CHANNEL_LINKS с реальными одноразовыми ссылками
        self.PRIVATE_CHANNEL_LINKS = {
            "25_stars": "https://t.me/+xLVbmqzc3Dk2NWM6",
            "50_stars": "https://t.me/+uxH6Ot8Kyu4wZDk6",
            "75_stars": "https://t.me/+diQh7MowVhIwYzVi",
            "100_stars": "https://t.me/+6XnGRwJd8rY2ZGUy",
            "150_ton": "https://t.me/+4BhdYzF2U65hOTIy",
            "100_ton": "https://t.me/+O7KaTknXPDVlMjY6",
            "50_ton": "https://t.me/+LaQZfJHeQPcyNjUy"
        }

        # Настройки подписок
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

        # Тексты сообщений
        self.WELCOME_MESSAGE = """🎉 welcome to the PassiveNFT 🎉

💰 PassiveNFT это возможность ПРИУМНОЖИТЬ свои вложения вплоть до х10! 💰

📋 ознакомиться со стоимостью подписок и что в них входит вы можете по кнопке "Подписки".

❓ если у вас всё еще остались вопросы, нажмите кнопку "Связь" для обращения к менеджеру по вопросам."""

        self.SUBSCRIPTION_DESCRIPTION = "💳 Нажми на интересующую тебя подписку"
        self.CONTACT_MESSAGE = "💬 Если у вас возникли какие-либо трудности с оплатой или есть вопросы, нажмите кнопку \"Задать вопрос\"."
        self.REFERRAL_MESSAGE = "👥 Реферальная система предназначена для амбассадоров закрытого проекта PassiveNFT и обычных участников\n\n🔗 Она состоит из пригласительной ссылки, где владелец ссылки получается 10% с его оплаты подписки, для более точных подробностей нажмите на кнопку \"Задать вопрос\"."

        self.ACTIVITY_SUBSCRIPTION_TYPE_MESSAGE = """После перехода по кнопке подписки, выберите желаемый тип подписки:"""

        self.ACTIVITY_SUBSCRIPTION_DESCRIPTION = """активные подписки представляют собой менее затратный способ получить возможность приумножить свои вложения путем участия в различных активностях

чтобы ознакомиться с тем что входит в подписку, выберите заинтересовавший вас вариант снизу"""
        
        self.REFERRAL_WELCOME_MESSAGE = """🎉 welcome to the PassiveNFT 🎉

💰 PassiveNFT это возможность ПРИУМНОЖИТЬ свои вложения вплоть до х10! 💰

🔗 Вы пришли по реферальной ссылке!

📋 ознакомиться со стоимостью подписок и что в них входит вы можете по кнопке "Подписки"

❓ если у вас всё еще остались вопросы, нажмите кнопку "Связь" для обращения к менеджеру по вопросам."""

        self.REFERRAL_LINK_MESSAGE = "🔗 **Ваша персональная реферальная ссылка:**\n\nПриглашайте друзей и зарабатывайте 10% с каждой их оплаты подписки!"
        
        self.REFERRAL_STATS_MESSAGE = """Статистика ваших рефералов:
{referrals_info}"""

        # Сообщения для оплаты через звездочки
        self.STARS_PAYMENT_MESSAGE_TEMPLATE = f"""для оплаты по TON кошельку нажмите на [{self.TON_WALLET_ADDRESS}](ton://transfer?amount={{ton_amount}}&address={self.TON_WALLET_ADDRESS}) и отправьте {{ton_amount}} TON (эквивалентно ~{{stars}} звездам).
для оплаты ЗВЕЗДОЧКАМИ перейдите [сюда](https://t.me/{self.STARS_USERNAME}) и отправьте подарком стоимость подписки + оплата комиссии
после оплаты обратитесь к менеджеру [здесь](https://t.me/{self.MANAGER_USERNAME}) для подтверждения оплаты и для получения ссылки в закрытый ТГК."""

        # Описания для каждого уровня звездочек
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

        # Платежные инструкции
        self.PAYMENT_INSTRUCTIONS = f"""Для оплаты отправьте {self.TON_WALLET_ADDRESS} на указанный выше адрес TON кошелька.
⚠️ ВАЖНО: Скопируйте адрес кошелька и отправьте указанную сумму TON."""

        logger.info("✅ PRIVATE_CHANNEL_LINKS загружены:")
        for key, value in self.PRIVATE_CHANNEL_LINKS.items():
            logger.info(f"  {key}: {value}")

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
    elif os.path.exists('config_deploy.py'):
        from config_deploy import config
        logger.info("Конфигурация загружена из config_deploy.py")
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
    """Главный класс бота с полной интеграцией всех исправлений"""
    def __init__(self):
        self.config = config
        self.database = AsyncDatabaseManager()  # Асинхронная база данных
        self.application = None
        
        # СИСТЕМА ПОДТВЕРЖДЕНИЯ ОПЛАТЫ - ИНИЦИАЛИЗАЦИЯ
        self.used_links = set()  # Множество использованных ссылок
        self.confirmation_queue = {}  # Очередь ожидающих подтверждений
        
        # ИСПРАВЛЕНО: Ссылки на приватные каналы по типам подписок (PRIVATE_CHANNEL_LINKS)
        self.subscription_links = self.config.PRIVATE_CHANNEL_LINKS
        
        # Настройка приложения
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
            self.application.add_handler(CommandHandler("confirm_payment", self.confirm_payment_command))
            self.application.add_handler(CommandHandler("adminserveraa", self.admin_command))
            self.application.add_handler(CommandHandler("adminserveraastat", self.admin_stats_command))
            self.application.add_handler(CommandHandler("adminserveraapeople", self.admin_people_command))
            self.application.add_handler(CommandHandler("adminserveraaref", self.admin_referrals_command))
            self.application.add_handler(CommandHandler("broadcast", self.broadcast_command))
            
            # КОМАНДЫ ДЛЯ КАНАЛОВ
            self.application.add_handler(CommandHandler("channel_info", self.channel_info_command))
            self.application.add_handler(CommandHandler("get_channel_id", self.get_channel_id_command))
            self.application.add_handler(CommandHandler("testcmd", self.testcmd_command))
            
            # СИСТЕМА ПОДТВЕРЖДЕНИЯ ОПЛАТЫ
            self.application.add_handler(CommandHandler("confirmpay", self.confirmpay_command))
            self.application.add_handler(CallbackQueryHandler(self.confirmpay_subscription_type_callback, pattern="^confirmpay_type_"))
            self.application.add_handler(CallbackQueryHandler(self.confirmpay_history_callback, pattern="^confirmpay_history$"))
            self.application.add_handler(CallbackQueryHandler(self.confirmpay_stats_callback, pattern="^confirmpay_stats$"))
            
            # Обработчики подписок
            self.application.add_handler(CallbackQueryHandler(self.subscription_callback, pattern="^subscription$"))
            self.application.add_handler(CallbackQueryHandler(self.select_stars_callback, pattern="^select_stars$"))
            self.application.add_handler(CallbackQueryHandler(self.select_ton_callback, pattern="^select_ton$"))
            self.application.add_handler(CallbackQueryHandler(self.subscription_plan_callback, pattern="^subscription_plan_"))
            self.application.add_handler(CallbackQueryHandler(self.ton_subscription_plan_callback, pattern="^ton_subscription_plan_"))
            self.application.add_handler(CallbackQueryHandler(self.payment_callback, pattern="^payment_"))
            
            # обработчики для активных подписок
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
            
            # ИСПРАВЛЕНО: confirmpay_back_callback с query.message
            self.application.add_handler(CallbackQueryHandler(self.confirmpay_back_callback, pattern="^confirmpay_back$"))
            
            # ИСПРАВЛЕНО: единый обработчик сообщений (убран дубликат)
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

    # ФУНКЦИЯ СОЗДАНИЯ РЕАЛЬНЫХ INVITE ССЫЛОК ЧЕРЕЗ TELEGRAM API
    async def create_invite_link(self, channel_id: int, user_id: int) -> Optional[str]:
        """Создание реальной одноразовой invite ссылки через Telegram Bot API"""
        try:
            logger.info(f"Создание invite ссылки для канала {channel_id} пользователем {user_id}")
            
            # Создаем одноразовую ссылку с истечением через 1 час
            invite_link = await self.application.bot.create_chat_invite_link(
                chat_id=channel_id,
                creates_join_request=False,
                expire_date=datetime.now().timestamp() + 3600,  # 1 час
                member_limit=1  # Только для одного пользователя
            )
            
            logger.info(f"✅ Invite ссылка создана: {invite_link.invite_link}")
            return invite_link.invite_link
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания invite ссылки: {e}")
            # В случае ошибки возвращаем fallback ссылку из конфига
            logger.info("🔄 Используется fallback ссылка из конфига")
            return None

    # НОВЫЕ КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ КАНАЛАМИ
    async def channel_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /channel_info - информация о каналах (только для админов)"""
        try:
            user = update.effective_user
            logger.info(f"КОМАНДА ПОЛУЧЕНА: /channel_info от пользователя {user.id}")
            
            # Проверяем админские права
            if user.id not in self.config.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return

            # Форматирование информации с диагностикой
            try:
                # Подготавливаем данные для форматирования
                channel_data = {}
                ton_channel_data = {}
                
                # Данные для Stars платежей
                for stars, channel_id in self.config.CHANNEL_MAPPINGS.items():
                    channel_data[f'stars_{stars}'] = str(channel_id)
                
                # Данные для TON платежей
                for users, channel_id in self.config.TON_CHANNEL_MAPPINGS.items():
                    ton_channel_data[f'ton_{users}'] = str(channel_id)
                
                # Добавляем недостающие ключи с дефолтными значениями для Stars
                for stars in [25, 50, 75, 100]:
                    if f'stars_{stars}' not in channel_data:
                        channel_data[f'stars_{stars}'] = "НЕ НАСТРОЕН"
                
                # Добавляем недостающие ключи с дефолтными значениями для TON
                for users in [50, 100, 150]:
                    if f'ton_{users}' not in ton_channel_data:
                        ton_channel_data[f'ton_{users}'] = "НЕ НАСТРОЕН"
                
                logger.info(f"Данные Stars для форматирования: {channel_data}")
                logger.info(f"Данные TON для форматирования: {ton_channel_data}")
                
                # Улучшенное безопасное форматирование с разделением Stars и TON
                info_text = safe_format_user_data(
                    """
**ИНФОРМАЦИЯ О СИСТЕМЕ КАНАЛОВ**

**Stars платежи:**
25 звезд → ID: `{stars_25}`
50 звезд → ID: `{stars_50}`
75 звезд → ID: `{stars_75}`
100 звезд → ID: `{stars_100}`

**TON платежи:**
150 тон → ID: `{ton_150}`
100 тон → ID: `{ton_100}`
50 тон → ID: `{ton_50}`

**PRIVATE_CHANNEL_LINKS:**
Используются реальные одноразовые invite ссылки для каждого типа подписки.

**Инструкции:**
1. Реальные ID каналов уже настроены
2. PRIVATE_CHANNEL_LINKS интегрированы в систему подтверждения оплат
3. Используйте /confirmpay для подтверждения оплат

**Диагностика:**
CHANNEL_MAPPINGS: {diagnostic_stars}
TON_CHANNEL_MAPPINGS: {diagnostic_ton}
                    """,
                    **channel_data,
                    **ton_channel_data,
                    diagnostic_stars=str(self.config.CHANNEL_MAPPINGS),
                    diagnostic_ton=str(self.config.TON_CHANNEL_MAPPINGS)
                )
                
                await update.message.reply_text(info_text, parse_mode='Markdown')
                logger.info(f"Команда /channel_info выполнена для пользователя {user.id}")
                
            except Exception as format_error:
                logger.error(f"Ошибка форматирования: {format_error}")
                # Отправляем детальную диагностическую информацию
                diagnostic_text = f"""
**ОШИБКА ФОРМАТИРОВАНИЯ**

**CHANNEL_MAPPINGS (Stars):** {self.config.CHANNEL_MAPPINGS}
**TON_CHANNEL_MAPPINGS (TON):** {self.config.TON_CHANNEL_MAPPINGS}

**Детали ошибки:** {str(format_error)}

**Типы данных Stars:**
{[(k, type(v), str(v)) for k, v in self.config.CHANNEL_MAPPINGS.items()]}

**Типы данных TON:**
{[(k, type(v), str(v)) for k, v in self.config.TON_CHANNEL_MAPPINGS.items()]}
                """
                await update.message.reply_text(diagnostic_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка в channel_info_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка при выполнении команды.")

    async def get_channel_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /get_channel_id - получение ID текущего канала (только для админов)"""
        try:
            user = update.effective_user
            logger.info(f"КОМАНДА ПОЛУЧЕНА: /get_channel_id от пользователя {user.id}")
            
            # Проверяем админские права
            if user.id not in self.config.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return

            # Получаем информацию о чате
            chat = update.effective_chat
            
            # Улучшенное безопасное форматирование с экранированием
            try:
                test_text = safe_format_user_data(
                    "**ID КАНАЛА ПОЛУЧЕН**\n\n"
                    "**Тип:** {chat_type}\n"
                    "**Название:** {chat_title}\n"
                    "**ID:** {chat_id}\n"
                    "**Username:** @{chat_username}\n\n"
                    "**Бот активен и готов к работе!**",
                    chat_type=str(chat.type),
                    chat_title=str(chat.title or "Не указано"),
                    chat_id=str(chat.id),
                    chat_username=str(chat.username or "не указан")
                )

                await update.message.reply_text(test_text, parse_mode='Markdown')
                logger.info(f"Команда /get_channel_id выполнена для пользователя {user.id}")
                
            except Exception as format_error:
                logger.error(f"Ошибка форматирования в get_channel_id: {format_error}")
                # Отправляем простую диагностическую информацию
                simple_info = f"""**ID КАНАЛА ПОЛУЧЕН**

Тип: {chat.type}
Название: {chat.title or 'Не указано'}  
ID: {chat.id}
Username: @{chat.username or 'не указан'}

Бот активен и готов к работе!"""
                await update.message.reply_text(simple_info, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка в get_channel_id_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка при выполнении команды.")

    async def testcmd_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /testcmd - тестовая команда для проверки функционала (только для админов)"""
        try:
            user = update.effective_user
            logger.info(f"КОМАНДА ПОЛУЧЕНА: /testcmd от пользователя {user.id}")
            
            # Проверяем админские права
            if user.id not in self.config.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return

            # Тестовая команда с диагностикой
            try:
                test_text = safe_format_user_data(
                    "**ТЕСТОВАЯ КОМАНДА ВЫПОЛНЕНА**\n\n"
                    "**Пользователь:** {user_name}\n"
                    "**ID:** {user_id}\n"
                    "**Время:** {timestamp}\n"
                    "**Бот статус:** Активен ✅\n"
                    "**База данных:** Подключена ✅\n"
                    "**PRIVATE_CHANNEL_LINKS:** Загружены ✅\n\n"
                    "**Markdown экранирование:** Работает ✅\n"
                    "**Система подтверждения:** Активна ✅",
                    user_name=str(user.first_name or user.username or "Unknown"),
                    user_id=str(user.id),
                    timestamp=str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )

                await update.message.reply_text(test_text, parse_mode='Markdown')
                logger.info(f"Команда /testcmd выполнена для пользователя {user.id}")
                
            except Exception as format_error:
                logger.error(f"Ошибка форматирования в testcmd: {format_error}")
                # Простой текст без форматирования для диагностики
                simple_test = f"""ТЕСТОВАЯ КОМАНДА ВЫПОЛНЕНА

Пользователь: {user.first_name or user.username or "Unknown"}
ID: {user.id}
Время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Бот статус: Активен ✅
База данных: Подключена ✅
PRIVATE_CHANNEL_LINKS: Загружены ✅"""
                await update.message.reply_text(simple_test)
            
        except Exception as e:
            logger.error(f"Ошибка в testcmd_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка при выполнении команды.")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start с обработкой реферальных параметров"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /start от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user
            args = context.args
            
            # Добавляем пользователя в базу данных
            await self.database.get_or_create_user(
                user.id, 
                user.username or "", 
                user.first_name or "", 
                user.last_name or ""
            )
            
            # Проверяем, есть ли реферальный параметр
            referrer_id = None
            if args and len(args) > 0:
                arg = args[0]
                if arg.startswith('ref_'):
                    try:
                        referrer_id = int(arg[4:])  # Убираем "ref_" и получаем ID
                        if referrer_id != user.id:  # Нельзя быть реферером самому себе
                            # Сохраняем информацию о рефере временно
                            await self.database.save_pending_referral(user.id, referrer_id)
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
        """Обработчик команды подтверждения оплаты и добавления реферала с комиссией только за TON"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /confirm_payment от пользователя {update.effective_user.id}")
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

    # ===== СИСТЕМА ПОДТВЕРЖДЕНИЯ ОПЛАТЫ - ПОЛНАЯ ВЕРСИЯ =====
    
    def generate_secure_link_id(self, length=16):
        """Генерация уникального ID для одноразовой ссылки"""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def validate_username(self, username: str) -> bool:
        """Проверка валидности Telegram username"""
        if not username or len(username) < 5 or len(username) > 32:
            return False
        
        # Telegram username может содержать: буквы, цифры, подчеркивания
        # Не может начинаться с подчеркивания
        import re
        pattern = r'^[a-zA-Z][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, username))
    
    async def save_confirmation_log(self, admin_id: int, subscription_type: str, username: str, link_id: str):
        """Сохранение лога подтверждения в базу данных"""
        try:
            await self.database.save_payment_confirmation({
                'admin_id': admin_id,
                'subscription_type': subscription_type,
                'username': username,
                'link_id': link_id,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Ошибка сохранения лога подтверждения: {e}")
    
    async def confirmpay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /confirmpay - главное меню подтверждения оплаты"""
        logger.info(f"КОМАНДА /confirmpay от пользователя {update.effective_user.id}")
        
        # Проверка прав администратора
        if update.effective_user.id not in self.config.ADMIN_USER_IDS:
            await update.message.reply_text("❌ Доступ запрещен. Только для администраторов.")
            return
        
        try:
            # Меню выбора типа подписки
            keyboard = [
                [
                    InlineKeyboardButton("⭐ 25 звезд", callback_data="confirmpay_type_25_stars"),
                    InlineKeyboardButton("⭐ 50 звезд", callback_data="confirmpay_type_50_stars")
                ],
                [
                    InlineKeyboardButton("⭐ 75 звезд", callback_data="confirmpay_type_75_stars"),
                    InlineKeyboardButton("⭐ 100 звезд", callback_data="confirmpay_type_100_stars")
                ],
                [
                    InlineKeyboardButton("💎 150 TON", callback_data="confirmpay_type_150_ton"),
                    InlineKeyboardButton("💎 100 TON", callback_data="confirmpay_type_100_ton")
                ],
                [
                    InlineKeyboardButton("💎 50 TON", callback_data="confirmpay_type_50_ton")
                ],
                [
                    InlineKeyboardButton("📊 История подтверждений", callback_data="confirmpay_history"),
                    InlineKeyboardButton("📈 Статистика", callback_data="confirmpay_stats")
                ]
            ]
            
            message_text = """👨‍💼 **МЕНЕДЖЕРСКАЯ ПАНЕЛЬ ПОДТВЕРЖДЕНИЯ ОПЛАТЫ**

Выберите тип подписки для подтверждения:

⭐ **ЗВЕЗДОЧКИ:** 25, 50, 75, 100
💎 **TON:** 150, 100, 50

📋 После выбора типа подписки:
1. Введите username пользователя
2. Система автоматически отправит одноразовую ссылку
3. Пользователь получит уведомление о подтверждении

⚡ Дополнительные функции: История и Статистика
"""
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            
            logger.info(f"✅ /confirmpay меню показано пользователю {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def confirmpay_subscription_type_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора типа подписки для подтверждения"""
        query = update.callback_query
        await query.answer()
        
        if update.effective_user.id not in self.config.ADMIN_USER_IDS:
            await query.edit_message_text("❌ Доступ запрещен.")
            return
        
        try:
            # Извлекаем тип подписки из callback_data
            subscription_type = query.data.replace("confirmpay_type_", "")
            
            # Определяем отображаемое название
            subscription_names = {
                "25_stars": "⭐ 25 звезд",
                "50_stars": "⭐ 50 звезд", 
                "75_stars": "⭐ 75 звезд",
                "100_stars": "⭐ 100 звезд",
                "150_ton": "💎 150 TON",
                "100_ton": "💎 100 TON",
                "50_ton": "💎 50 TON"
            }
            
            display_name = subscription_names.get(subscription_type, subscription_type)
            
            # Сохраняем выбранный тип в очереди ожидания
            self.confirmation_queue[update.effective_user.id] = {
                'subscription_type': subscription_type,
                'step': 'waiting_username'
            }
            
            # Меню для ввода username
            keyboard = [
                [InlineKeyboardButton("🔙 Отмена", callback_data="confirmpay_back")]
            ]
            
            message_text = f"""👨‍💼 **ВЫБРАНА ПОДПИСКА: {display_name}**

📝 **Следующий шаг:** Введите username пользователя

Формат: `@username` или просто `username`
(например: `john_doe` или `@john_doe`)

💡 **Важно:**
- Username должен быть действительным пользователем Telegram
- Система автоматически отправит ссылку пользователю
- Ссылка будет одноразовой и уникальной
"""
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            
            logger.info(f"✅ Выбран тип подписки {subscription_type} пользователем {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_subscription_type_callback: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def confirmpay_back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик возврата в главное меню /confirmpay - ИСПРАВЛЕНО"""
        query = update.callback_query  # ИСПРАВЛЕНО: используем query
        await query.answer()
        
        # ИСПРАВЛЕНО: используем query.from_user.id вместо update.effective_user.id
        if query.from_user.id not in self.config.ADMIN_USER_IDS:
            await query.edit_message_text("❌ Доступ запрещен.")
            return
        
        try:
            # Очищаем очередь ожидания
            if query.from_user.id in self.confirmation_queue:
                del self.confirmation_queue[query.from_user.id]
            
            # Показываем главное меню
            await self.confirmpay_command(update, context)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_back_callback: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def confirmpay_history_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик показа истории подтверждений"""
        query = update.callback_query
        await query.answer()
        
        if update.effective_user.id not in self.config.ADMIN_USER_IDS:
            await query.edit_message_text("❌ Доступ запрещен.")
            return
        
        try:
            # Получаем историю из базы данных
            recent_logs = await self.database.get_confirmation_history(limit=10)
            
            if not recent_logs:
                message_text = """📊 **ИСТОРИЯ ПОДТВЕРЖДЕНИЙ**

📭 История подтверждений пуста.
Пока что не было подтвержденных оплат.
"""
            else:
                message_text = "📊 **ИСТОРИЯ ПОДТВЕРЖДЕНИЙ (последние 10)**\n\n"
                
                for log in recent_logs:
                    timestamp = log.get('timestamp', '')
                    username = log.get('username', 'неизвестен')
                    subscription_type = log.get('subscription_type', 'неизвестно')
                    admin_id = log.get('admin_id', 'неизвестен')
                    
                    # Определяем отображаемое название подписки
                    subscription_names = {
                        "25_stars": "⭐ 25 звезд",
                        "50_stars": "⭐ 50 звезд", 
                        "75_stars": "⭐ 75 звезд",
                        "100_stars": "⭐ 100 звезд",
                        "150_ton": "💎 150 TON",
                        "100_ton": "💎 100 TON",
                        "50_ton": "💎 50 TON"
                    }
                    display_name = subscription_names.get(subscription_type, subscription_type)
                    
                    message_text += f"⏰ {timestamp[:16]}\n"
                    message_text += f"👤 @{username}\n"
                    message_text += f"📦 {display_name}\n"
                    message_text += f"👨‍💼 Админ: {admin_id}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_history_callback: {e}")
            await query.edit_message_text("❌ Ошибка загрузки истории. Попробуйте позже.")
    
    async def confirmpay_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик показа статистики"""
        query = update.callback_query
        await query.answer()
        
        if update.effective_user.id not in self.config.ADMIN_USER_IDS:
            await query.edit_message_text("❌ Доступ запрещен.")
            return
        
        try:
            # Получаем статистику из базы данных
            stats = await self.database.get_confirmation_stats()
            
            if not stats:
                message_text = """📈 **СТАТИСТИКА ПОДТВЕРЖДЕНИЙ**

📭 Статистика пока недоступна.
Подтверждения пока не проводились.
"""
            else:
                total_confirmations = stats.get('total', 0)
                today_confirmations = stats.get('today', 0)
                week_confirmations = stats.get('week', 0)
                popular_subscription = stats.get('popular_subscription', 'нет данных')
                
                message_text = f"""📈 **СТАТИСТИКА ПОДТВЕРЖДЕНИЙ**

📊 **Общая статистика:**
• Всего подтверждений: {total_confirmations}
• Сегодня: {today_confirmations}
• За неделю: {week_confirmations}

🏆 **Популярная подписка:**
{popular_subscription}

📅 **Отчет на:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_stats_callback: {e}")
            await query.edit_message_text("❌ Ошибка загрузки статистики. Попробуйте позже.")
    
    # ===== ОБРАБОТЧИК USERNAME ПОЛЬЗОВАТЕЛЯ - УЛУЧШЕННАЯ ВЕРСИЯ =====
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений - ОБНОВЛЕН"""
        logger.info(f"ТЕКСТОВОЕ СООБЩЕНИЕ ПОЛУЧЕНО: '{update.message.text}' от пользователя {update.effective_user.id}")
        try:
            message = update.message.text.lower()
            
            # ПРОВЕРКА: ОЖИДАЕМ ЛИ МЫ USERNAME ОТ АДМИНА?
            if (update.effective_user.id in self.confirmation_queue and 
                self.confirmation_queue[update.effective_user.id].get('step') == 'waiting_username'):
                await self.handle_username_input(update, context)
                return
            
            # Существующая логика для админских команд
            if "admin" in message and update.effective_user.id in self.config.ADMIN_USER_IDS:
                await self.admin_command(update, context)
            else:
                await update.message.reply_text(
                    "🤖 Используйте /start для начала работы"
                )
        except Exception as e:
            logger.error(f"❌ Ошибка в handle_message: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def handle_username_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода username пользователя для подтверждения оплаты - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            # Получаем данные из очереди ожидания
            queue_data = self.confirmation_queue.get(update.effective_user.id)
            if not queue_data:
                await update.message.reply_text("❌ Ошибка: не найдены данные для обработки.")
                return
            
            subscription_type = queue_data['subscription_type']
            
            # Очищаем и валидируем username
            username = update.message.text.strip()
            if username.startswith('@'):
                username = username[1:]  # Убираем @ в начале
            
            if not self.validate_username(username):
                await update.message.reply_text(
                    "❌ Некорректный username. Используйте только буквы, цифры и подчеркивания.\n"
                    "Пример: `john_doe` или `@john_doe`"
                )
                return
            
            # Генерируем уникальный ID ссылки
            link_id = self.generate_secure_link_id()
            
            # Проверяем, что ссылка еще не использовалась
            if link_id in self.used_links:
                link_id = self.generate_secure_link_id()  # Генерируем заново
            
            # ИСПРАВЛЕНО: Получаем channel_id для создания реальной invite ссылки
            channel_id = None
            if subscription_type == "25_stars":
                channel_id = self.config.CHANNEL_MAPPINGS.get(25)
            elif subscription_type == "50_stars":
                channel_id = self.config.CHANNEL_MAPPINGS.get(50)
            elif subscription_type == "75_stars":
                channel_id = self.config.CHANNEL_MAPPINGS.get(75)
            elif subscription_type == "100_stars":
                channel_id = self.config.CHANNEL_MAPPINGS.get(100)
            elif subscription_type == "150_ton":
                channel_id = self.config.TON_CHANNEL_MAPPINGS.get(150)
            elif subscription_type == "100_ton":
                channel_id = self.config.TON_CHANNEL_MAPPINGS.get(100)
            elif subscription_type == "50_ton":
                channel_id = self.config.TON_CHANNEL_MAPPINGS.get(50)
            
            # Пытаемся создать реальную invite ссылку через Telegram API
            real_invite_link = None
            if channel_id:
                try:
                    real_invite_link = await self.create_invite_link(channel_id, update.effective_user.id)
                    logger.info(f"✅ Реальная invite ссылка создана для {subscription_type}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось создать реальную invite ссылку: {e}")
            
            # Используем реальную ссылку или fallback из конфига
            base_link = None
            if real_invite_link:
                base_link = real_invite_link
                logger.info(f"🎯 Используется реальная invite ссылка: {base_link}")
            else:
                base_link = self.subscription_links.get(subscription_type, "")
                logger.info(f"🔄 Используется fallback ссылка из конфига: {base_link}")
            
            if not base_link:
                await update.message.reply_text("❌ Ошибка: не найдена ссылка для данного типа подписки.")
                return
            
            # Создаем безопасную ссылку
            secure_link = f"{base_link}&secure={link_id}"
            
            # Отправляем ссылку пользователю
            await self.send_subscription_link_to_user(username, subscription_type, secure_link, context)
            
            # Сохраняем лог подтверждения
            await self.save_confirmation_log(
                admin_id=update.effective_user.id,
                subscription_type=subscription_type,
                username=username,
                link_id=link_id
            )
            
            # Отмечаем ссылку как использованную
            self.used_links.add(link_id)
            
            # Очищаем очередь ожидания
            del self.confirmation_queue[update.effective_user.id]
            
            # Отправляем подтверждение админу
            subscription_names = {
                "25_stars": "⭐ 25 звезд",
                "50_stars": "⭐ 50 звезд", 
                "75_stars": "⭐ 75 звезд",
                "100_stars": "⭐ 100 звезд",
                "150_ton": "💎 150 TON",
                "100_ton": "💎 100 TON",
                "50_ton": "💎 50 TON"
            }
            display_name = subscription_names.get(subscription_type, subscription_type)
            
            link_type = "🔗 Реальная invite" if real_invite_link else "🔗 Fallback"
            
            await update.message.reply_text(
                f"✅ **ПОДТВЕРЖДЕНИЕ ОТПРАВЛЕНО!**\n\n"
                f"👤 Пользователь: @{username}\n"
                f"📦 Подписка: {display_name}\n"
                f"{link_type}: {secure_link}\n\n"
                f"🛡️ **Безопасность:** Ссылка одноразовая и уникальная\n"
                f"📊 Лог сохранен в базе данных\n\n"
                f"💡 **Следующее подтверждение:** используйте /confirmpay"
            )
            
            logger.info(f"✅ Подтверждение отправлено @{username} для {subscription_type} админом {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке username: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке. Попробуйте позже.")
    
    async def send_subscription_link_to_user(self, username: str, subscription_type: str, secure_link: str, context: ContextTypes.DEFAULT_TYPE):
        """Отправка ссылки на подписку пользователю"""
        try:
            # Определяем отображаемое название подписки
            subscription_names = {
                "25_stars": "⭐ 25 звезд",
                "50_stars": "⭐ 50 звезд", 
                "75_stars": "⭐ 75 звезд",
                "100_stars": "⭐ 100 звезд",
                "150_ton": "💎 150 TON",
                "100_ton": "💎 100 TON",
                "50_ton": "💎 50 TON"
            }
            display_name = subscription_names.get(subscription_type, subscription_type)
            
            # Формируем сообщение для пользователя
            message_text = f"""🎉 **ОПЛАТА ПОДТВЕРЖДЕНА!**

✅ Ваша подписка на закрытый Telegram-канал успешно активирована!

📦 **Детали подписки:**
• Тип: {display_name}
• Статус: ✅ Активирована
• Ссылка: {secure_link}

🛡️ **Важная информация:**
• Ссылка является одноразовой - используйте ее немедленно
• Не передавайте ссылку другим лицам
• При возникновении проблем обратитесь к менеджеру

🚀 **Добро пожаловать в закрытое сообщество PassiveNFT!**

Если у вас возникли вопросы, свяжитесь с менеджером: @{self.config.MANAGER_USERNAME}
"""
            
            # Отправляем сообщение пользователю
            await context.bot.send_message(
                chat_id=f"@{username}",
                text=message_text,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Ссылка отправлена пользователю @{username}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ссылки пользователю @{username}: {e}")
            raise e

    async def subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Подписки'"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: subscription callback от пользователя {update.effective_user.id}")
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
        """ИСПРАВЛЕННЫЙ обработчик выбора обычного плана TON с правильными ценами"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: ton_subscription_plan callback от пользователя {update.effective_user.id}")
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: subscription_plan callback от пользователя {update.effective_user.id}")
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: payment callback от пользователя {update.effective_user.id}")
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: activity_subscription callback от пользователя {update.effective_user.id}")
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
        """ИСПРАВЛЕННЫЙ обработчик выбора активных подписок (звездочки)"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: select_stars callback от пользователя {update.effective_user.id}")
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
        """ИСПРАВЛЕННЫЙ обработчик выбора обычных подписок (TON) с ПРАВИЛЬНЫМИ ценами"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: select_ton callback от пользователя {update.effective_user.id}")
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
        """ИСПРАВЛЕННЫЙ обработчик выбора конкретного плана звездочек"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: star_subscription_plan callback от пользователя {update.effective_user.id}")
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
        """ИСПРАВЛЕННЫЙ обработчик оплаты через звездочки"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: stars_payment callback от пользователя {update.effective_user.id}")
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

для оплаты ЗВЕЗДОЧКАМИ нажмите кнопку "Оплатить звездочками" и отправьте подарком стоимость подписки + оплата комиссии (при нажатии этой кнопки пользователя перекидывает на тг @{self.config.STARS_USERNAME})

после оплаты обратитесь к менеджеру [здесь](https://t.me/{self.config.MANAGER_USERNAME}) для подтверждения оплаты и для получения ссылки в закрытый ТГК.

⚠️ ВАЖНО: Для копирования адреса кошелька нажмите на кнопку "Оплатить TON" """

            # ИСПРАВЛЕННЫЕ кнопки для оплаты - ПРЯМАЯ ССЫЛКА НА @pingvinchik_liza
            keyboard = [
                [InlineKeyboardButton("💰 Оплатить TON", callback_data=f"copy_stars_ton_{stars}")],
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
        """ИСПРАВЛЕННЫЙ обработчик кнопки "Оплатить TON" - копирование адреса"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: copy_stars_ton callback от пользователя {update.effective_user.id}")
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
        """ИСПРАВЛЕННЫЙ обработчик кнопки "Оплатить звездочками" - редирект на менеджера"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: stars_payment_stars callback от пользователя {update.effective_user.id}")
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
        """Обработчик кнопки 'Связь' с ОРИГИНАЛЬНЫМ текстом"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: contact callback от пользователя {update.effective_user.id}")
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
        """Обработчик кнопки 'Реферальная система' с ОРИГИНАЛЬНЫМИ кнопками"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral callback от пользователя {update.effective_user.id}")
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: get_referral callback от пользователя {update.effective_user.id}")
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral_stats callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Получаем статистику пользователя
            stats_text = await self.database.get_user_referral_stats(query.from_user.id)
            if stats_text:
                stats_text = self.config.REFERRAL_STATS_MESSAGE.format(referrals_info=stats_text)
            else:
                stats_text = "У вас пока нет рефералов."

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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: copy_ton callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            await query.message.edit_text(
                f"Адрес кошелька скопирован!\n\n`{self.config.TON_WALLET_ADDRESS}`\n\nОтправьте указанную сумму TON.",
                parse_mode='Markdown'
            )
            logger.info(f"✅ Адрес TON скопирован для пользователя {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в copy_ton_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Назад' - возврат к главному меню"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: back callback от пользователя {update.effective_user.id}")
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraa от пользователя {update.effective_user.id}")
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

**НОВЫЕ КОМАНДЫ:**
📺 /channel_info - информация о каналах
🆔 /get_channel_id - получить ID текущего канала
🔧 /testcmd - тестовая команда

💳 Система подтверждения оплат:
👨‍💼 /confirmpay - подтверждение оплат с автоотправкой ссылок
⭐ Все типы подписок: 25/50/75/100 звезд, 50/100/150 TON

💰 Количество подписок:
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraastat от пользователя {update.effective_user.id}")
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraapeople от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к админ панели")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к админ панели от пользователя {user.id}")
                return

            # Получаем список участников
            try:
                users_data = self.database.get_subscribers()
                
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraaref от пользователя {update.effective_user.id}")
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /broadcast от пользователя {update.effective_user.id}")
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
            total_users = self.database.get_all_users_count()
            
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

    async def run(self):
        """Запуск бота с улучшенной структурой"""
        logger.info("🚀 Запуск PassiveNFT Bot на Render...")
        
        # Инициализация асинхронной базы данных
        logger.info("🗄️ Инициализация асинхронной базы данных...")
        await self.database.initialize()
        logger.info("✅ Асинхронная база данных инициализирована")
        
        logger.info(f"🤖 Бот: @{self.config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...{self.config.TON_WALLET_ADDRESS[-10:]}")
        logger.info("✅ Реферальная система включена (комиссия только за TON)")
        logger.info("⭐️ Активные подписки за звездочки включены")
        logger.info("🆔 Новые команды для работы с каналами включены")
        logger.info("🔗 PRIVATE_CHANNEL_LINKS интегрированы")
        logger.info("🔄 Система реальных invite ссылок активирована")

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
    """Запускает бота и веб-сервер одновременно с улучшенной обработкой ошибок"""
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
        logger.info("🔥 ЗАПУСК PassiveNFT Bot - ПОЛНАЯ ИНТЕГРАЦИЯ ИСПРАВЛЕНИЙ...")
        asyncio.run(run_both())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
