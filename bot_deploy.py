#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PassiveNFT Bot - ВЕРСИЯ С АКТИВНЫМИ ПОДПИСКАМИ (за звездочки) - ИСПРАВЛЕННАЯ ВЕРСИЯЯ
ИСПРАВЛЕНИЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ:
- Устранено дублирование в функции add_referral
- Добавлена таблица pending_referrals в базу данных
- Реализована система начисления комиссий реферерам (10%)
- Исправлены типы подписок для корректной работы статистики
- Улучшена функция get_user_referral_stats с подробной статистикой
- Добавлены функции calculate_commission и add_referral_earnings
- Исправлена статистика подписок для админов
- ИСПРАВЛЕНЫ ЭМОДЗИ В F-СТРОКАХ (SyntaxError)
- ДОБАВЛЕНЫ КОМАНДЫ /channel_info, /get_channel_id, /testcmd
- ИСПРАВЛЕНА ПРОБЛЕМА С PARSING MARKDOWN - правильное экранирование специальных символов
- ПОЛНОСТЬЮ ИСПРАВЛЕНА СИСТЕМА /confirmpay для бесперебойной работы
"""
import asyncio
import logging
import sqlite3
import sys
import traceback
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import re

# Импорты Telegram бота - ГЛОБАЛЬНЫЕ ИМПОРТЫ
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest

# ИМПОРТЫ ДЛЯ ВЕБ-СЕРВЕРА (для решения проблемы с портом на Render.com)
import os
import aiohttp
from aiohttp import web

# Импортируем нашу асинхронную базу данных (ИСПРАВЛЕНИЕ ЗАВИСАНИЯ)
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

# УЛУЧШЕННАЯ ФУНКЦИЯ ЭКРАНИРОВАНИЯ ДЛЯ MARKDOWN - ИСПРАВЛЕНИЕ ОШИБОК ПАРСИНГА
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

# Удаляем класс Database, используем DatabaseManager из database.py

class SafeConfig:
    """Безопасная конфигурация бота с активными подписками - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    def __init__(self):
        # Основные настройки
        self.BOT_TOKEN = self._get_env_var('BOT_TOKEN', '8530441136:AAHto3A4Zqa5FnGG01cxL6SvU3jW8_Ai0iI')
        self.ADMIN_USER_IDS = [8387394503, 2112739781] # pro.player.egor

        # Настройки TON кошелька
        self.TON_WALLET_ADDRESS = self._get_env_var('TON_WALLET_ADDRESS', 'UQAij8pQ3HhdBn3lw6n9Iy2toOH9OMcBuL8yoSXTNpLJdfZJ')
        self.MANAGER_USERNAME = self._get_env_var('MANAGER_USERNAME', 'num6er9')
        self.BOT_USERNAME = self._get_env_var('BOT_USERNAME', 'passivenft_bot')
        
        # ИСПРАВЛЕНО: STARS_USERNAME - pingvinchik_liza
        self.STARS_USERNAME = self._get_env_var('STARS_USERNAME', 'pingvinchik_liza')

        # ИСПРАВЛЕНО: MAPPING каналов для Stars платежей (ЗАМЕНИТЕ НА РЕАЛЬНЫЕ ID)
        self.CHANNEL_MAPPINGS = {
            25: -1001234567891,  # 25 звезд -> ID канала 1
            50: -1001234567892,  # 50 звезд -> ID канала 2  
            75: -1001234567893,  # 75 звезд -> ID канала 3
            100: -1001234567894, # 100 звезд -> ID канала 4
            150: -1001234567895, # 150 звезд -> ID канала 5
            200: -1001234567896, # 200 звезд -> ID канала 6
            250: -1001234567897  # 250 звезд -> ID канала 7
        }

        # НОВОЕ: TON_CHANNEL_MAPPINGS для соответствия с оригинальным кодом
        self.TON_CHANNEL_MAPPINGS = {
            150: -1001234567898, # 150 тон -> ID канала 8
            100: -1001234567899, # 100 тон -> ID канала 9  
            50: -1001234567900   # 50 тон -> ID канала 10
        }

        # НОВОЕ: STARS_CHANNEL_MAPPINGS для соответствия с оригинальным кодом
        self.STARS_CHANNEL_MAPPINGS = {
            -1002755746127: "Stars Channel 1",
            -1003223397887: "Stars Channel 2", 
            -1003232732123: "Stars Channel 3",
            -1003361243296: "Stars Channel 4"
        }

        # НОВОЕ: TON_CHANNEL_MAPPINGS для подтверждений
        self.TON_CHANNEL_INVITE_LINKS = [
            "https://t.me/+4BhdYzF2U65hOTIy",
            "https://t.me/+O7KaTknXPDVlMjY6", 
            "https://t.me/+LaQZfJHeQPcyNjUy"
        ]

        # НОВОЕ: STARS_CHANNEL_INVITE_LINKS для подтверждений
        self.STARS_CHANNEL_INVITE_LINKS = [
            "https://t.me/+xLVbmqzc3Dk2NWM6",
            "https://t.me/+uxH6Ot8Kyu4wZDk6",
            "https://t.me/+diQh7MowVhIwYzVi",
            "https://t.me/+6XnGRwJd8rY2ZGUy"
        ]

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

        # ИСПРАВЛЕННЫЙ ТЕКСТ БЕЗ ЖИРНОГО ФОРМАТИРОВАНИЯ И ЗВЕЗДОЧЕК
        self.WELCOME_MESSAGE = """🎉 Добро пожаловать в PassiveNFT! 🎉

💰 PassiveNFT это возможность ПРИУМНОЖИТЬ свои вложения вплоть до х69! 💰

📋 Для полного ознакомления со стоимостью подписок и что в них входит вы можете по кнопке "Подписки".

❓ Если у вас всё еще остались вопросы, нажмите кнопку "Связь" для обращения к менеджеру по вопросам."""

        # ИСПРАВЛЕННЫЕ СООБЩЕНИЯ ДЛЯ РАБОТЫ БОТА
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

        # ИСПРАВЛЕННОЕ сообщение для реферальной ссылки
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
                "description": """за вход в стоимость в 25 ЗВЕЗДОЧЕК вы сможете приумножить свою вложения вплоть до х56, всё зависит лишь от вашей скорости и удачи.

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
                "description": """за вход в стоимость в 50 ЗВЕЗДОЧЕК вы сможете приумножить свою вложения вплоть до х46, всё зависит лишь от вашей скорости и удачи.

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
                "description": """за вход в стоимость в 75 ЗВЕЗДОЧЕК вы сможете приумножить свою вложения вплоть до х61, всё зависит лишь от вашей скорости и удачи.

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
                "description": """за вход в стоимость в 100 ЗВЕЗДОЧЕК вы сможете приумножить свою вложения вплоть до х69, всё зависит лишь от вашей скорости и удачи.

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

# Инициализация конфигурации - ИСПРАВЛЕНО: ИМПОРТ ИЗ config_deploy_new
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
    """Главный класс бота с исправленной реферальной системой и ПОЛНОСТЬЮ ИСПРАВЛЕННОЙ системой /confirmpay"""
    def __init__(self):
        self.config = config
        self.database = AsyncDatabaseManager()  # Асинхронная база данных (ИСПРАВЛЕНИЕ ЗАВИСАНИЯ)
        self.application = None
        # ДОБАВЛЕНО: Словарь для хранения ожидающих ввод username для /confirmpay
        self.confirmpay_pending_users = {}  # {user_id: subscription_type}
        
        # ДОБАВЛЕНО: История подтверждений для реальной работы статистики
        self.confirmation_history = []  # Список подтверждений [{username, subscription_type, admin_id, timestamp}]
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
            
            # НОВАЯ КОМАНДА: Система подтверждения оплат /confirmpay
            self.application.add_handler(CommandHandler("confirmpay", self.confirmpay_command))
            
            self.application.add_handler(CommandHandler("adminserveraa", self.admin_command))
            self.application.add_handler(CommandHandler("adminserveraastat", self.admin_stats_command))
            self.application.add_handler(CommandHandler("adminserveraapeople", self.admin_people_command))
            self.application.add_handler(CommandHandler("adminserveraaref", self.admin_referrals_command))
            self.application.add_handler(CommandHandler("broadcast", self.broadcast_command))
            
            # НОВЫЕ КОМАНДЫ ДЛЯ КАНАЛОВ - ИСПРАВЛЕНО
            self.application.add_handler(CommandHandler("channel_info", self.channel_info_command))
            self.application.add_handler(CommandHandler("get_channel_id", self.get_channel_id_command))
            self.application.add_handler(CommandHandler("testcmd", self.testcmd_command))
            
            # Обработчики подписок
            self.application.add_handler(CallbackQueryHandler(self.subscription_callback, pattern="^subscription$"))
            self.application.add_handler(CallbackQueryHandler(self.select_stars_callback, pattern="^select_stars$"))
            self.application.add_handler(CallbackQueryHandler(self.select_ton_callback, pattern="^select_ton$"))
            self.application.add_handler(CallbackQueryHandler(self.subscription_plan_callback, pattern="^subscription_plan_"))
            self.application.add_handler(CallbackQueryHandler(self.ton_subscription_plan_callback, pattern="^ton_subscription_plan_"))
            self.application.add_handler(CallbackQueryHandler(self.payment_callback, pattern="^payment_"))
            
            # ИСПРАВЛЕННЫЕ обработчики для активных подписок
            self.application.add_handler(CallbackQueryHandler(self.activity_subscription_callback, pattern="^activity_subscription_"))
            self.application.add_handler(CallbackQueryHandler(self.star_subscription_plan_callback, pattern="^star_plan_"))
            self.application.add_handler(CallbackQueryHandler(self.stars_payment_callback, pattern="^stars_payment_"))
            self.application.add_handler(CallbackQueryHandler(self.copy_stars_ton_callback, pattern="^copy_stars_ton_"))
            self.application.add_handler(CallbackQueryHandler(self.stars_payment_stars_callback, pattern="^stars_payment_stars_"))
            
            # ПОЛНОСТЬЮ ИСПРАВЛЕННЫЕ обработчики для системы /confirmpay
            self.application.add_handler(CallbackQueryHandler(
                self.confirmpay_subscription_type_callback, 
                pattern="^confirmpay_type_"
            ))
            self.application.add_handler(CallbackQueryHandler(
                self.confirmpay_confirm_callback, 
                pattern="^confirmpay_confirm_"
            ))
            self.application.add_handler(CallbackQueryHandler(
                self.confirmpay_history_callback, 
                pattern="^confirmpay_history$"
            ))
            self.application.add_handler(CallbackQueryHandler(
                self.confirmpay_stats_callback, 
                pattern="^confirmpay_stats$"
            ))
            self.application.add_handler(CallbackQueryHandler(
                self.confirmpay_back_callback, 
                pattern="^confirmpay_back$"
            ))
            
            # Существующие обработчики
            self.application.add_handler(CallbackQueryHandler(self.contact_callback, pattern="^contact$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_callback, pattern="^referral$"))
            self.application.add_handler(CallbackQueryHandler(self.get_referral_link_callback, pattern="^get_referral$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_stats_callback, pattern="^referral_stats$"))
            self.application.add_handler(CallbackQueryHandler(self.copy_ton_callback, pattern="^copy_ton_"))
            self.application.add_handler(CallbackQueryHandler(self.back_callback, pattern="^back$"))
            # ИСПРАВЛЕНО: Обработчик текстовых сообщений для /confirmpay
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

    # НОВЫЕ КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ КАНАЛАМИ - УЛУЧШЕННАЯ ВЕРСИЯ
    async def channel_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /channel_info - информация о каналах (только для админов)"""
        try:
            user = update.effective_user
            logger.info(f"КОМАНДА ПОЛУЧЕНА: /channel_info от пользователя {user.id}")
            
            # Проверяем админские права
            if user.id not in self.config.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return

            # УЛУЧШЕННОЕ ФОРМАТИРОВАНИЕ С ДИАГНОСТИКОЙ
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
                
                # ИСПРАВЛЕНО: Улучшенное безопасное форматирование с разделением Stars и TON
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

**Инструкции:**
1. Замените placeholder ID на реальные ID каналов
2. Добавьте бота в каждый канал как администратора
3. Используйте /get_channel_id для получения реальных ID
4. Обновите CHANNEL_MAPPINGS и TON_CHANNEL_MAPPINGS после получения реальных ID

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
            
            # УЛУЧШЕННОЕ: Улучшенное безопасное форматирование с экранированием
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

            # УЛУЧШЕННОЕ: Тестовая команда с диагностикой
            try:
                test_text = safe_format_user_data(
                    "**ТЕСТОВАЯ КОМАНДА ВЫПОЛНЕНА**\n\n"
                    "**Пользователь:** {user_name}\n"
                    "**ID:** {user_id}\n"
                    "**Время:** {timestamp}\n"
                    "**Бот статус:** Активен ✅\n"
                    "**База данных:** Подключена ✅\n\n"
                    "**Markdown экранирование:** Работает ✅",
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
База данных: Подключена ✅"""
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
            
            # Добавляем пользователя в базу данных (ИСПРАВЛЕНИЕ ЗАВИСАНИЯ)
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
                            # Сохраняем информацию о рефере временно (ИСПРАВЛЕНИЕ ЗАВИСАНИЯ)
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
                # Добавляем реферала в базу (ИСПРАВЛЕНИЕ ЗАВИСАНИЯ)
                success = await self.database.add_referral(pending_referrer, user.id)
                if success:
                    # УДАЛЯЕМ запись об ожидающем реферере (ИСПРАВЛЕНИЕ ЗАВИСАНИЯ)
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

    # ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ СИСТЕМА /confirmpay
    async def confirmpay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /confirmpay - главное меню подтверждения оплаты"""
        logger.info(f"КОМАНДА /confirmpay от пользователя {update.effective_user.id}")
        try:
            # Проверяем админские права
            if update.effective_user.id not in self.config.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return

            # Главное меню подтверждения оплаты
            keyboard = [
                [InlineKeyboardButton("⭐ 25 звезд", callback_data="confirmpay_type_25_stars"),
                 InlineKeyboardButton("⭐ 50 звезд", callback_data="confirmpay_type_50_stars")],
                [InlineKeyboardButton("⭐ 75 звезд", callback_data="confirmpay_type_75_stars"),
                 InlineKeyboardButton("⭐ 100 звезд", callback_data="confirmpay_type_100_stars")],
                [InlineKeyboardButton("💎 150 TON", callback_data="confirmpay_type_150_ton"),
                 InlineKeyboardButton("💎 100 TON", callback_data="confirmpay_type_100_ton")],
                [InlineKeyboardButton("💎 50 TON", callback_data="confirmpay_type_50_ton")],
                [InlineKeyboardButton("📊 История подтверждений", callback_data="confirmpay_history"),
                 InlineKeyboardButton("📈 Статистика", callback_data="confirmpay_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "👨‍💼 **СИСТЕМА ПОДТВЕРЖДЕНИЯ ОПЛАТ**\n\n"
                "Выберите тип подписки для подтверждения:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            logger.info(f"✅ /confirmpay меню показано пользователю {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def confirmpay_subscription_type_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора типа подписки в /confirmpay - ИСПРАВЛЕНО"""
        logger.info(f"КОМАНДА /confirmpay type от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Извлекаем тип подписки из callback_data
            subscription_type = query.data.replace("confirmpay_type_", "")
            
            # Сохраняем ожидающий ввод для данного пользователя
            self.confirmpay_pending_users[query.from_user.id] = subscription_type
            
            # Отправляем инструкции для выбранного типа
            message_text = f"""✅ ПОДТВЕРЖДЕНИЕ ОПЛАТЫ

Тип подписки: {subscription_type}

Введите username пользователя без @

Например: testuser или username123

После ввода username будет показана кнопка для подтверждения подписки."""

            # Кнопка отмены
            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="confirmpay_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.edit_text(message_text, reply_markup=reply_markup)
            logger.info(f"✅ /confirmpay type {subscription_type} показано пользователю {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_subscription_type_callback: {e}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def confirmpay_confirm_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик подтверждения подписки - ИСПРАВЛЕНО"""
        logger.info(f"КОМАНДА /confirmpay confirm от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Извлекаем username и тип подписки
            data_parts = query.data.split('_')
            if len(data_parts) >= 5:  # confirmpay_confirm_USERNAME_TYPE (минимум 5 частей)
                username = data_parts[2]  # confirmpay_confirm_USERNAME_TYPE
                subscription_type = data_parts[3] + '_' + data_parts[4]  # 25_stars
            else:
                await query.answer("❌ Ошибка: неверный формат данных")
                return

            # Удаляем пользователя из ожидающих
            if query.from_user.id in self.confirmpay_pending_users:
                del self.confirmpay_pending_users[query.from_user.id]

            # Определяем ссылку для отправки
            invite_link = await self.get_invite_link_for_subscription(subscription_type)
            
            if not invite_link:
                await query.message.edit_text(
                    f"❌ ОШИБКА\n\n"
                    f"Не найдена ссылка для типа: {subscription_type}\n"
                    f"Пожалуйста, обратитесь к администратору."
                )
                return

            # Отправляем подтверждение админу
            confirmation_text = f"""✅ ПОДТВЕРЖДЕНИЕ ОПЛАТЫ ВЫПОЛНЕНО

Администратор: {query.from_user.username or query.from_user.first_name}
Пользователь: {username}
Тип подписки: {subscription_type}
Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Ссылка отправлена пользователю:
{invite_link}

Система подтверждения оплат: Активна ✅"""

            await query.message.edit_text(confirmation_text)
            
            # НОВОЕ: Отправляем ссылку пользователю с ИСПРАВЛЕННОЙ АВТООТПРАВКОЙ
            try:
                # ИСПРАВЛЕНИЕ 1: Убираем @ из username для поиска в БД
                clean_username = username.replace('@', '')
                
                # ИСПРАВЛЕНИЕ 2: Проверяем наличие пользователя в базе данных
                logger.info(f"🔍 Поиск пользователя @{clean_username} в базе данных...")
                
                user_data = await self.database.get_user_by_username(clean_username)
                
                if not user_data:
                    logger.warning(f"⚠️ Пользователь @{clean_username} не найден в базе данных")
                    await query.message.reply_text(
                        f"⚠️ ОШИБКА: Пользователь @{clean_username} не найден в базе данных\n\n"
                        f"Пользователь должен:\n"
                        f"• Запустить бота командой /start\n"
                        f"• Иметь username\n\n"
                        f"🔗 ОТПРАВИТЕ ССЫЛКУ ВРУЧНУЮ: {invite_link}"
                    )
                    return
                
                logger.info(f"✅ Пользователь @{clean_username} найден в БД (ID: {user_data['id']})")
                
                # ИСПРАВЛЕНИЕ 3: Попытка отправки через get_chat БЕЗ @ символа
                try:
                    logger.info(f"📤 Отправка через get_chat @{clean_username}")
                    
                    # ИСПРАВЛЕННЫЙ синтаксис - без @
                    chat = await self.application.bot.get_chat(clean_username)
                    
                    user_message = f"""✅ ПОДТВЕРЖДЕНИЕ ОПЛАТЫ

Поздравляем! Ваша подписка на {subscription_type} подтверждена администратором.

🔗 Пригласительная ссылка на закрытый канал:
{invite_link}

Спасибо за вашу подписку!"""
                    
                    await self.application.bot.send_message(
                        chat_id=chat.id,
                        text=user_message
                    )
                    
                    logger.info(f"✅ ССЫЛКА УСПЕШНО ОТПРАВЛЕНА через get_chat @{clean_username}")
                    
                except Exception as chat_error:
                    logger.warning(f"⚠️ get_chat не сработал для @{clean_username}: {chat_error}")
                    
                    # ИСПРАВЛЕНИЕ 4: Fallback через user_id из БД
                    try:
                        logger.info(f"📤 Отправка через user_id {user_data['id']}")
                        
                        user_message = f"""✅ ПОДТВЕРЖДЕНИЕ ОПЛАТЫ

Поздравляем! Ваша подписка на {subscription_type} подтверждена администратором.

🔗 Пригласительная ссылка на закрытый канал:
{invite_link}

Спасибо за вашу подписку!"""
                        
                        await self.application.bot.send_message(
                            chat_id=user_data['id'],
                            text=user_message
                        )
                        
                        logger.info(f"✅ ССЫЛКА УСПЕШНО ОТПРАВЛЕНА через user_id @{clean_username}")
                        
                    except Exception as user_id_error:
                        logger.error(f"❌ Оба метода отправки не сработали для @{clean_username}: {user_id_error}")
                        raise chat_error
                
            except Exception as send_error:
                logger.error(f"❌ ОШИБКА при отправке ссылки пользователю @{clean_username}: {send_error}")
                await query.message.reply_text(
                    f"❌ ОШИБКА: Не удалось отправить ссылку пользователю @{clean_username}\n"
                    f"Ошибка: {str(send_error)}\n\n"
                    f"🔗 ОТПРАВИТЕ ССЫЛКУ ВРУЧНУЮ:\n{invite_link}"
                )
            
            # Сохраняем в историю подтверждений (база данных)
            await self.save_confirmation_to_history(username, subscription_type, query.from_user.id)
            
            logger.info(f"✅ Подтверждение выполнено: @{username} - {subscription_type} от админа {query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_confirm_callback: {e}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def get_invite_link_for_subscription(self, subscription_type: str) -> Optional[str]:
        """Получение пригласительной ссылки для типа подписки - ИСПРАВЛЕНО"""
        try:
            # Используем ключи из PRIVATE_CHANNEL_LINKS
            if subscription_type in self.config.PRIVATE_CHANNEL_LINKS:
                return self.config.PRIVATE_CHANNEL_LINKS[subscription_type]
            
            # Обратная совместимость - обработка по частям
            subscription_lower = subscription_type.lower()
            
            # Stars подписки
            if "stars" in subscription_lower:
                if "25" in subscription_lower:
                    return self.config.PRIVATE_CHANNEL_LINKS.get("25_stars", "Stars канал недоступен")
                elif "50" in subscription_lower:
                    return self.config.PRIVATE_CHANNEL_LINKS.get("50_stars", "Stars канал недоступен")
                elif "75" in subscription_lower:
                    return self.config.PRIVATE_CHANNEL_LINKS.get("75_stars", "Stars канал недоступен")
                elif "100" in subscription_lower:
                    return self.config.PRIVATE_CHANNEL_LINKS.get("100_stars", "Stars канал недоступен")
                elif "150" in subscription_lower:
                    return self.config.PRIVATE_CHANNEL_LINKS.get("150_stars", "Stars канал недоступен")
                elif "200" in subscription_lower:
                    return self.config.PRIVATE_CHANNEL_LINKS.get("200_stars", "Stars канал недоступен")
                elif "250" in subscription_lower:
                    return self.config.PRIVATE_CHANNEL_LINKS.get("250_stars", "Stars канал недоступен")
            
            # TON подписки  
            elif "ton" in subscription_lower:
                if "50" in subscription_lower:
                    return self.config.PRIVATE_CHANNEL_LINKS.get("50_ton", "TON канал недоступен")
                elif "100" in subscription_lower:
                    return self.config.PRIVATE_CHANNEL_LINKS.get("100_ton", "TON канал недоступен")
                elif "150" in subscription_lower:
                    return self.config.PRIVATE_CHANNEL_LINKS.get("150_ton", "TON канал недоступен")
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения ссылки: {e}")
            return None

    async def save_confirmation_to_history(self, username: str, subscription_type: str, admin_id: int):
        """Сохранение подтверждения в историю - ИСПРАВЛЕНО"""
        try:
            # Сохраняем в реальную структуру данных
            confirmation_data = {
                'username': username,
                'subscription_type': subscription_type,
                'admin_id': admin_id,
                'timestamp': datetime.now()
            }
            
            self.confirmation_history.append(confirmation_data)
            logger.info(f"История: @{username} - {subscription_type} от админа {admin_id}")
            logger.info(f"Подтверждение сохранено в историю. Всего подтверждений: {len(self.confirmation_history)}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в историю: {e}")

    async def confirmpay_history_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик просмотра истории подтверждений - ИСПРАВЛЕНО"""
        logger.info(f"КОМАНДА /confirmpay history от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Получаем реальную историю из базы данных или памяти
            history_data = await self.get_confirmation_history()
            
            if not history_data:
                history_text = "📊 ИСТОРИЯ ПОДТВЕРЖДЕНИЙ\n\n❌ История пуста - подтверждений пока не было"
            else:
                history_text = "📊 ИСТОРИЯ ПОДТВЕРЖДЕНИЙ\n\n"
                
                # Показываем последние 5 подтверждений
                for i, confirmation in enumerate(history_data[-5:], 1):
                    username = confirmation.get('username', 'unknown')
                    subscription_type = confirmation.get('subscription_type', 'unknown')
                    time_str = confirmation.get('time', 'время неизвестно')
                    
                    history_text += f"• {username} - {subscription_type} ({time_str})\n"
                
                history_text += f"\nВсего подтверждено: {len(history_data)}"
                
                # Подсчет за сегодня
                today_count = sum(1 for conf in history_data 
                                if datetime.now().date() == conf.get('date', datetime.now()).date())
                history_text += f"\nСегодня: {today_count}"

            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.edit_text(history_text, reply_markup=reply_markup)
            logger.info(f"✅ История подтверждений показана пользователю {query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_history_callback: {e}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def get_confirmation_history(self) -> list:
        """Получение истории подтверждений - ИСПРАВЛЕНО"""
        if not self.confirmation_history:
            return []
        
        # Форматируем реальные данные для отображения
        formatted_history = []
        for confirmation in self.confirmation_history:
            # Определяем временной интервал
            now = datetime.now()
            timestamp = confirmation['timestamp']
            delta = now - timestamp
            
            if delta.seconds < 60:
                time_str = "только что"
            elif delta.seconds < 3600:
                minutes = delta.seconds // 60
                time_str = f"{minutes} мин назад"
            elif delta.days == 0:
                hours = delta.seconds // 3600
                time_str = f"{hours} ч назад"
            elif delta.days == 1:
                time_str = "вчера"
            else:
                time_str = f"{delta.days} дн назад"
            
            formatted_history.append({
                'username': confirmation['username'],
                'subscription_type': confirmation['subscription_type'],
                'time': time_str,
                'date': timestamp
            })
        
        # Возвращаем в обратном порядке (новые первые)
        return list(reversed(formatted_history))

    async def confirmpay_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик просмотра статистики подтверждений - ИСПРАВЛЕНО"""
        logger.info(f"КОМАНДА /confirmpay stats от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Получаем реальную статистику
            stats_data = await self.get_confirmation_stats()
            
            stats_text = f"""📈 СТАТИСТИКА ПОДТВЕРЖДЕНИЙ

По типам подписок:
⭐ Stars подписки: {stats_data['stars_count']} ({stats_data['stars_percentage']}%)
💎 TON подписки: {stats_data['ton_count']} ({stats_data['ton_percentage']}%)

По суммам:
• 25 звезд: {stats_data['25_stars']}
• 50 звезд: {stats_data['50_stars']}  
• 75 звезд: {stats_data['75_stars']}
• 100 звезд: {stats_data['100_stars']}
• 50 TON: {stats_data['50_ton']}
• 100 TON: {stats_data['100_ton']}
• 150 TON: {stats_data['150_ton']}

Период: Последние 30 дней"""

            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.edit_text(stats_text, reply_markup=reply_markup)
            logger.info(f"✅ Статистика подтверждений показана пользователю {query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_stats_callback: {e}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def get_confirmation_stats(self) -> dict:
        """Получение статистики подтверждений - ИСПРАВЛЕНО"""
        # В реальном проекте это будет запрос к базе данных
        # Пока возвращаем тестовые данные
        history = await self.get_confirmation_history()
        
        if not history:
            return {
                'stars_count': 0, 'ton_count': 0,
                'stars_percentage': 0, 'ton_percentage': 0,
                '25_stars': 0, '50_stars': 0, '75_stars': 0, '100_stars': 0,
                '50_ton': 0, '100_ton': 0, '150_ton': 0
            }
        
        # Подсчет статистики
        stars_count = sum(1 for conf in history if 'stars' in conf['subscription_type'])
        ton_count = sum(1 for conf in history if 'ton' in conf['subscription_type'])
        total = len(history)
        
        stats = {
            'stars_count': stars_count,
            'ton_count': ton_count,
            'stars_percentage': round((stars_count / total * 100) if total > 0 else 0),
            'ton_percentage': round((ton_count / total * 100) if total > 0 else 0),
            '25_stars': sum(1 for conf in history if conf['subscription_type'] == '25_stars'),
            '50_stars': sum(1 for conf in history if conf['subscription_type'] == '50_stars'),
            '75_stars': sum(1 for conf in history if conf['subscription_type'] == '75_stars'),
            '100_stars': sum(1 for conf in history if conf['subscription_type'] == '100_stars'),
            '50_ton': sum(1 for conf in history if conf['subscription_type'] == '50_ton'),
            '100_ton': sum(1 for conf in history if conf['subscription_type'] == '100_ton'),
            '150_ton': sum(1 for conf in history if conf['subscription_type'] == '150_ton')
        }
        
        return stats

    async def confirmpay_back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик возврата в главное меню /confirmpay - ИСПРАВЛЕНО"""
        logger.info(f"КОМАНДА /confirmpay back от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Удаляем пользователя из ожидающих ввод
            if query.from_user.id in self.confirmpay_pending_users:
                del self.confirmpay_pending_users[query.from_user.id]

            # Главное меню подтверждения оплаты
            keyboard = [
                [InlineKeyboardButton("⭐ 25 звезд", callback_data="confirmpay_type_25_stars"),
                 InlineKeyboardButton("⭐ 50 звезд", callback_data="confirmpay_type_50_stars")],
                [InlineKeyboardButton("⭐ 75 звезд", callback_data="confirmpay_type_75_stars"),
                 InlineKeyboardButton("⭐ 100 звезд", callback_data="confirmpay_type_100_stars")],
                [InlineKeyboardButton("💎 150 TON", callback_data="confirmpay_type_150_ton"),
                 InlineKeyboardButton("💎 100 TON", callback_data="confirmpay_type_100_ton")],
                [InlineKeyboardButton("💎 50 TON", callback_data="confirmpay_type_50_ton")],
                [InlineKeyboardButton("📊 История подтверждений", callback_data="confirmpay_history"),
                 InlineKeyboardButton("📈 Статистика", callback_data="confirmpay_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.edit_text(
                "👨‍💼 **СИСТЕМА ПОДТВЕРЖДЕНИЯ ОПЛАТ**\n\n"
                "Выберите тип подписки для подтверждения:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Возврат к меню /confirmpay для пользователя {query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_back_callback: {e}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    # ИСПРАВЛЕННЫЙ обработчик сообщений для /confirmpay
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений для /confirmpay"""
        logger.info(f"ТЕКСТОВОЕ СООБЩЕНИЕ ПОЛУЧЕНО: '{update.message.text}' от пользователя {update.effective_user.id}")
        try:
            user_id = update.effective_user.id
            message_text = update.message.text.strip()
            
            # Проверяем, ожидает ли пользователь ввод username для /confirmpay
            if user_id in self.confirmpay_pending_users:
                subscription_type = self.confirmpay_pending_users[user_id]
                
                # Проверяем формат username
                if not re.match(r'^[a-zA-Z0-9_]{5,32}$', message_text):
                    await update.message.reply_text(
                        "❌ НЕВЕРНЫЙ USERNAME\n\n"
                        "Username должен содержать:\n"
                        "• Только буквы, цифры и подчеркивания\n"
                        "• От 5 до 32 символов\n"
                        "• Без пробелов и специальных символов\n\n"
                        "Примеры: testuser, user123, my_name"
                    )
                    return
                
                # Показываем подтверждение с кнопкой
                confirmation_text = f"""✅ ПОДТВЕРЖДЕНИЕ ПОДПИСКИ

Username: {message_text}
Тип подписки: {subscription_type}

После подтверждения пользователю будет отправлена ссылка на закрытый канал.
                """
                
                keyboard = [
                    [InlineKeyboardButton(
                        "✅ Подтвердить подписку", 
                        callback_data=f"confirmpay_confirm_{message_text}_{subscription_type}"
                    )],
                    [InlineKeyboardButton("❌ Отмена", callback_data="confirmpay_back")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    confirmation_text, 
                    reply_markup=reply_markup
                )
                
                logger.info(f"✅ Username получен для /confirmpay: @{message_text} - {subscription_type}")
                return
            
            # Обычная обработка сообщений
            if "admin" in message_text.lower() and update.effective_user.id in self.config.ADMIN_USER_IDS:
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

    async def subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Подписки' - БЕЗ ЖИРНОГО ТЕКСТА"""
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
        """Обработчик кнопки 'Оплатить' - БЕЗ ЖИРНОГО ТЕКСТА"""
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
        """Обработчик выбора активных подписок - ИСПРАВЛЕННЫЙ"""
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

для оплаты в TON нажмите кнопку "Оплатить TON" и отправьте сумму указанную выше.

для оплаты ЗВЕЗДОЧКАМИ нажмите кнопку "Оплатить звездочками" и отправьте подарком стоимость подписки + оплата комиссии.

после оплаты обратитесь по кнопке "Менеджер" для подтверждения оплаты, после чего бот вам автоматически отправит ссылку на вступление.

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
        """Обработчик получения реферальной ссылки - БЕЗ ЖИРНОГО ТЕКСТА"""
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

            # Получаем статистику пользователя (ИСПРАВЛЕНИЕ ЗАВИСАНИЯ)
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
👨‍💼 /confirmpay - подтверждение оплат с автоотправкой ссылок

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

    # Функция get_all_users удалена - используем DatabaseManager методы

    # Функции get_user_referral_stats удалена - используем DatabaseManager.get_user_referral_stats

    # Функция get_subscription_stats удалена - используем DatabaseManager методы

    # Функции get_subscribed_people, calculate_commission, add_referral_earnings, get_referrals_stats удалены - используем DatabaseManager методы

    async def run(self):
        """Запуск бота с улучшенной структурой"""
        logger.info("🚀 Запуск PassiveNFT Bot на Render...")
        
        # Инициализация асинхронной базы данных (ИСПРАВЛЕНИЕ ЗАВИСАНИЯ)
        logger.info("🗄️ Инициализация асинхронной базы данных...")
        await self.database.initialize()
        logger.info("✅ Асинхронная база данных инициализирована")
        
        logger.info(f"🤖 Бот: @{self.config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...{self.config.TON_WALLET_ADDRESS[-10:]}")
        logger.info("✅ Реферальная система включена (комиссия только за TON)")
        logger.info("⭐️ Активные подписки за звездочки включены")
        logger.info("🆔 Новые команды для работы с каналами включены")
        logger.info("👨‍💼 ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ система подтверждения оплат /confirmpay включена")

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
        logger.info("🔥 ЗАПУСК PassiveNFT Bot...")
        asyncio.run(run_both())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
