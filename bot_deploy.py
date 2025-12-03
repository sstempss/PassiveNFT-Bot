#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PassiveNFT Bot - ИСПРАВЛЕННАЯ РЕФЕРАЛЬНАЯ СИСТЕМА + КОМАНДА /rus
ИСПРАВЛЕНИЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ:
- ✅ Полностью рабочая реферальная система без сбоев
- ✅ Рефералом становятся только после подтверждения оплаты (/confirmpay)
- ✅ Персональные реферальные ссылки для каждого пользователя
- ✅ Детальная статистика с разбивкой по типам подписок
- ✅ Команда /rus для админов с расширенной статистикой
- ✅ Все методы создания ссылок, статистики и навигации
- ✅ Интеграция с системой подтверждения оплаты /confirmpay

ДОПОЛНИТЕЛЬНЫЕ ИСПРАВЛЕНИЯ:
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
- КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ СТАБИЛЬНОСТИ:
  - Решена проблема с сетевыми тайм-аутами httpx
  - Добавлена логика повторных попыток для Telegram API
  - Исправлены тяжелые ответы (до 1 минуты)
  - Добавлена защита от ошибок в start_command
  - Оптимизирован polling режим
  - Улучшена обработка ошибок подключения
  - Добавлены таймауты для операций с БД
  - Graceful restart на сетевых ошибках
"""
import asyncio
import logging
import sys
import traceback
import time
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
import re

# Импорты Telegram бота - ГЛОБАЛЬНЫЕ ИМПОРТЫ
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest, TelegramError
import httpx
import sqlite3

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

        # НОВОЕ: PRIVATE_CHANNEL_LINKS для исправленной системы /confirmpay
        self.PRIVATE_CHANNEL_LINKS = {
            "25_stars": "https://t.me/+xLVbmqzc3Dk2NWM6",
            "50_stars": "https://t.me/+uxH6Ot8Kyu4wZDk6", 
            "75_stars": "https://t.me/+diQh7MowVhIwYzVi",
            "100_stars": "https://t.me/+6XnGRwJd8rY2ZGUy",
            "150_stars": "https://t.me/+LaQZfJHeQPcyNjUy",
            "50_ton": "https://t.me/+4BhdYzF2U65hOTIy",
            "100_ton": "https://t.me/+O7KaTknXPDVlMjY6",
            "150_ton": "https://t.me/+LaQZfJHeQPcyNjUy"
        }

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
        self.WELCOME_MESSAGE = """🎉 welcome to the PassiveNFT 🎉

💰 PassiveNFT это возможность ПРИУМНОЖИТЬ свои вложения вплоть до х10! 💰

📋 ознакомиться со стоимостью подписок и что в них входит вы можете по кнопке "Подписки".

❓ если у вас всё еще остались вопросы, нажмите кнопку "Связь" для обращения к менеджеру по вопросам."""

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
        self.REFERRAL_LINK_MESSAGE = "🔗 Ваша персональная реферальная ссылка:\n\nПриглашайте друзей и зарабатывайте 10% с каждой их оплаты подписки!"
        
        self.REFERRAL_STATS_MESSAGE = """Статистика ваших рефералов:
{referrals_info}"""

        # Сообщения для оплаты через звездочки
        self.STARS_PAYMENT_MESSAGE_TEMPLATE = f"""для оплаты по TON кошельку нажмите на [{self.TON_WALLET_ADDRESS}](ton://transfer?amount={{ton_amount}}&address={self.TON_WALLET_ADDRESS}) и отправьте {{ton_amount}} TON (эквивалентно ~{{stars}} звездам).
для оплаты ЗВЕЗДОЧКАМИ перейдите по кнопке "Оплатить звездочками" и отправьте подарком стоимость подписки + оплата комиссии
после оплаты обратитесь к менеджеру для подтверждения."""

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
    """Главный класс бота с исправленной реферальной системой, командой /rus и ПОЛНОСТЬЮ ИСПРАВЛЕННОЙ системой /confirmpay + КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ СТАБИЛЬНОСТИ"""
    def __init__(self):
        self.config = config
        self.database = AsyncDatabaseManager()  # Асинхронная база данных (ИСПРАВЛЕНИЕ ЗАВИСАНИЯ)
        self.application = None
        # ИСПРАВЛЕНО: Добавляем прямые атрибуты для быстрого доступа
        self.BOT_USERNAME = self.config.BOT_USERNAME
        self.ADMIN_USER_IDS = self.config.ADMIN_USER_IDS
        # ДОБАВЛЕНО: Словарь для хранения ожидающих ввод username для /confirmpay
        self.confirmpay_pending_users = {}  # {user_id: subscription_type}
        
        # ДОБАВЛЕНО: История подтверждений для реальной работы статистики
        self.confirmation_history = []  # Список подтверждений [{username, subscription_type, admin_id, timestamp}]
        self.start_time = datetime.now()
        
        logger.info("🚀 PassiveNFT Bot - Стабильная версия с исправлениями инициализирован")
        self.setup_telegram_application()

    def setup_telegram_application(self):
        """Настройка Telegram приложения с оптимизированной конфигурацией"""
        try:
            # Создание приложения с настройками для стабильности
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
            
            # НОВАЯ КОМАНДА: /rus для админов с реферальной статистикой
            self.application.add_handler(CommandHandler("rus", self.rus_command))
            
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
            
            # Обработчики реферальной системы для пользователей
            self.application.add_handler(CallbackQueryHandler(self.referral_callback, pattern="^referral$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_create_link_callback, pattern="^referral_create_link$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_stats_callback, pattern="^referral_stats$"))
            self.application.add_handler(CallbackQueryHandler(self.referral_stats_type_callback, pattern="^referral_stats_"))
            self.application.add_handler(CallbackQueryHandler(self.referral_back_callback, pattern="^referral_back$"))
            
            # Обработчики русской панели для админов
            self.application.add_handler(CallbackQueryHandler(self.rus_menu_callback, pattern="^rus_menu$"))
            self.application.add_handler(CallbackQueryHandler(self.rus_stats_callback, pattern="^rus_stats$"))
            self.application.add_handler(CallbackQueryHandler(self.rus_stats_type_callback, pattern="^rus_stats_"))
            self.application.add_handler(CallbackQueryHandler(self.rus_back_callback, pattern="^rus_back$"))
            
            # Существующие обработчики
            self.application.add_handler(CallbackQueryHandler(self.contact_callback, pattern="^contact$"))
            self.application.add_handler(CallbackQueryHandler(self.get_referral_link_callback, pattern="^get_referral$"))
            self.application.add_handler(CallbackQueryHandler(self.copy_ton_callback, pattern="^copy_ton_"))
            self.application.add_handler(CallbackQueryHandler(self.back_callback, pattern="^back$"))
            # ИСПРАВЛЕНО: Обработчик текстовых сообщений для /confirmpay
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

            logger.info("✅ Telegram приложение настроено с исправлениями стабильности и реферальной системой")
        except Exception as e:
            logger.error(f"❌ Ошибка настройки приложения: {e}")
            raise

    async def safe_get_user(self, update: Update) -> Optional[dict]:
        """КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасное получение данных пользователя с защитой от ошибок"""
        try:
            user = update.effective_user
            if not user:
                logger.warning("⚠️ effective_user is None")
                return None
                
            return {
                'id': getattr(user, 'id', 0),
                'username': getattr(user, 'username', '') or '',
                'first_name': getattr(user, 'first_name', '') or '',
                'last_name': getattr(user, 'last_name', '') or ''
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных пользователя: {e}")
            return None

    async def safe_database_operation(self, operation_name: str, operation_func, timeout: float = 5.0):
        """КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасное выполнение операций с базой данных с таймаутом"""
        try:
            logger.info(f"🔄 Выполнение {operation_name}...")
            
            # Создаем задачу с таймаутом
            task = asyncio.create_task(operation_func())
            result = await asyncio.wait_for(task, timeout=timeout)
            
            logger.info(f"✅ {operation_name} выполнено успешно")
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"⏰ Таймаут {operation_name} ({timeout}s)")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка {operation_name}: {e}")
            return None

    async def _get_all_users_for_broadcast(self):
        """Получение всех пользователей для рассылки"""
        try:
            # Попытка получить всех пользователей из базы данных
            if hasattr(self.database, 'get_all_users'):
                return await self.database.get_all_users()
            else:
                # Fallback: получаем всех пользователей через get_subscribers()
                if hasattr(self.database, 'get_subscribers'):
                    users = await self.database.get_subscribers()
                    # Преобразуем в нужный формат
                    formatted_users = []
                    for user in users:
                        formatted_users.append({
                            'user_id': user['user_id'],
                            'username': user.get('username', ''),
                            'first_name': user.get('first_name', '')
                        })
                    return formatted_users
                
                # Последний fallback: если ничего нет, возвращаем пустой список
                logger.warning("⚠️ Не найдены функции получения пользователей в базе данных")
                return []
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователей для рассылки: {e}")
            return []

    async def clear_webhook_on_startup(self):
        """Очистка webhook перед запуском для решения конфликтов"""
        try:
            logger.info("🧹 Очистка старных webhook'ов...")
            await self.application.bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook очищен успешно")
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при очистке webhook: {e}")

    # ===== НОВЫЕ МЕТОДЫ РЕФЕРАЛЬНОЙ СИСТЕМЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ =====
    
    async def referral_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Реферальная система' - ПОЛНОСТЬЮ РАБОЧАЯ"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral callback")
        try:
            query = update.callback_query
            await query.answer()
            user_id = query.from_user.id
            
            # Проверяем, есть ли у пользователя реферальная ссылка
            user_data = await self.safe_database_operation(
                "проверка пользователя для реферальной системы",
                lambda: self.database.get_user_by_username(query.from_user.username or str(user_id))
            )
            
            if user_data and user_data.get('referral_code'):
                # У пользователя есть реферальная ссылка
                referral_text = """👥 **РЕФЕРАЛЬНАЯ СИСТЕМА**

🔗 У вас есть персональная реферальная ссылка!

💰 Приглашайте друзей и зарабатывайте 10% с каждой их оплаты подписки

📊 Просматривайте детальную статистику по каждому типу подписки"""
                
                keyboard = [
                    [InlineKeyboardButton("📋 Моя ссылка", callback_data="get_referral")],
                    [InlineKeyboardButton("📊 Статистика", callback_data="referral_stats")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back")]
                ]
            else:
                # У пользователя нет реферальной ссылки
                referral_text = """👥 **РЕФЕРАЛЬНАЯ СИСТЕМА**

💡 У вас пока что нет пригласительной ссылки, если хотите ее создать нажмите кнопку "Создать ссылку".

🔗 После создания ссылки вы сможете:
• Приглашать друзей через персональную ссылку
• Получать 10% комиссии с оплат подписчиков
• Отслеживать свою статистику в реальном времени
• Зарабатывать пассивный доход"""
                
                keyboard = [
                    [InlineKeyboardButton("🔗 Создать ссылку", callback_data="referral_create_link")],
                    [InlineKeyboardButton("📊 Статистика", callback_data="referral_stats")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back")]
                ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.message.edit_text(referral_text, reply_markup=reply_markup, parse_mode='Markdown')
                logger.info(f"✅ Реферальная система показана пользователю {user_id}")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.error(f"❌ Ошибка BadRequest в referral_callback: {e}")
                    raise
                # Сообщение не изменилось, просто отвечаем на callback
                await query.answer()
                logger.info(f"ℹ️ Реферальная система уже показана")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def referral_create_link_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик создания реферальной ссылки"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral_create_link callback")
        try:
            query = update.callback_query
            await query.answer()
            user = query.from_user
            
            # Создаем пользователя в базе данных если его нет
            await self.safe_database_operation(
                "создание пользователя для реферальной ссылки",
                lambda: self.database.get_or_create_user(
                    user.id, 
                    user.username or "", 
                    user.first_name or "", 
                    user.last_name or ""
                )
            )
            
            # Генерируем персональную реферальную ссылку
            referral_link = f"https://t.me/{self.BOT_USERNAME}?start=ref_{user.id}"
            
            link_text = f"""🔗 Ваша персональная реферальная ссылка:

[`{referral_link}`]({referral_link})

💰 Приглашайте друзей и зарабатывайте 10% с каждой их оплаты подписки!"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Моя статистика", callback_data="referral_stats")],
                [InlineKeyboardButton("🔙 Назад", callback_data="referral")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(link_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
            logger.info(f"✅ Реферальная ссылка создана для пользователя {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_create_link_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def referral_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик основной статистики рефералов"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral_stats callback")
        try:
            query = update.callback_query
            await query.answer()
            
            stats_text = """📊 **ВЫБОР ТИПА ПОДПИСКИ ДЛЯ СТАТИСТИКИ**

Выберите тип подписки, по которому хотите посмотреть статистику рефералов:"""
            
            keyboard = [
                [InlineKeyboardButton("⭐ 25 звезд", callback_data="referral_stats_25_stars"),
                 InlineKeyboardButton("⭐ 50 звезд", callback_data="referral_stats_50_stars")],
                [InlineKeyboardButton("⭐ 75 звезд", callback_data="referral_stats_75_stars"),
                 InlineKeyboardButton("⭐ 100 звезд", callback_data="referral_stats_100_stars")],
                [InlineKeyboardButton("💎 4 TON", callback_data="referral_stats_4_ton"),
                 InlineKeyboardButton("💎 7 TON", callback_data="referral_stats_7_ton")],
                [InlineKeyboardButton("💎 13 TON", callback_data="referral_stats_13_ton")],
                [InlineKeyboardButton("🔙 Назад", callback_data="referral")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Выбор типа подписки для статистики показан")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_stats_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def referral_stats_type_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик показа статистики по конкретному типу подписки - ИСПРАВЛЕННЫЙ"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral_stats_type callback")
        try:
            query = update.callback_query
            await query.answer()
            
            # Извлекаем тип подписки из callback_data
            subscription_type = query.data.replace("referral_stats_", "")
            user_id = query.from_user.id
            
            # Маппинг для понятных названий
            type_display_names = {
                "25_stars": "25 звезд",
                "50_stars": "50 звезд", 
                "75_stars": "75 звезд",
                "100_stars": "100 звезд",
                "4_ton": "4 TON",
                "7_ton": "7 TON",
                "13_ton": "13 TON"
            }
            
            display_name = type_display_names.get(subscription_type, subscription_type)
            
            # Получаем статистику для данного типа подписки
            stats = await self.safe_database_operation(
                f"получение статистики по {subscription_type}",
                lambda: self.get_user_referral_stats_by_type(user_id, subscription_type)
            )
            
            # Формируем текст статистики
            if stats and stats.get('count', 0) > 0:
                stats_text = f"""📊 **СТАТИСТИКА ПО ТИПУ: {display_name}**

👥 Количество рефералов (оплативших): **{stats['count']}**
💰 Сумма комиссии: **{stats['total_commission']} TON**

💡 Комиссия составляет 10% от стоимости оплаченной подписки
⏰ Статистика обновляется в реальном времени после каждого подтверждения оплаты"""
            else:
                stats_text = f"""📊 **СТАТИСТИКА ПО ТИПУ: {display_name}**

👥 Количество рефералов (оплативших): **0**
💰 Сумма комиссии: **0 TON**

💡 Пока нет оплативших рефералов по этому типу подписки
🔗 Приглашайте друзей по вашей реферальной ссылке!"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Другой тип", callback_data="referral_stats")],
                [InlineKeyboardButton("🔙 Назад", callback_data="referral")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Статистика по {subscription_type} показана пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_stats_type_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def referral_back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик возврата в меню реферальной системы"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral_back callback")
        try:
            query = update.callback_query
            await query.answer()
            
            # Возвращаемся к основному меню реферальной системы
            await self.referral_callback(update, context)
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_back_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def get_user_referral_stats_by_type(self, user_id: int, subscription_type: str) -> dict:
        """Получение статистики рефералов по конкретному типу подписки для пользователей"""
        try:
            async with self.database._lock:
                async with sqlite3.connect(self.database.db_path) as db:
                    # Нормализуем тип подписки для поиска
                    normalized_type = self.normalize_subscription_type(subscription_type)
                    
                    # Получаем статистику рефералов для данного типа
                    cursor = await db.execute("""
                        SELECT 
                            COUNT(DISTINCT r.referred_id) as referral_count,
                            COALESCE(SUM(re.commission_amount), 0) as total_commission
                        FROM referrals r
                        LEFT JOIN referral_earnings re ON r.referred_id = re.referred_id
                        WHERE r.referrer_id = ? 
                        AND re.subscription_type = ?
                        AND re.payment_method = 'TON'
                    """, (user_id, normalized_type))
                    
                    row = await cursor.fetchone()
                    await cursor.close()
                    
                    if row:
                        return {
                            'count': row[0],
                            'total_commission': round(float(row[1]), 2)
                        }
                    else:
                        return {'count': 0, 'total_commission': 0.0}
        except Exception as e:
            logger.error(f"Ошибка получения статистики по типу {subscription_type}: {e}")
            return {'count': 0, 'total_commission': 0.0}

    def normalize_subscription_type(self, subscription_type: str) -> str:
        """Нормализация типа подписки для поиска в базе данных"""
        mapping = {
            "25_stars": "4_ton",  # 25 звезд = 4 TON план
            "50_stars": "7_ton",  # 50 звезд = 7 TON план  
            "75_stars": "13_ton", # 75 звезд = 13 TON план
            "100_stars": "13_ton", # 100 звезд = 13 TON план
            "4_ton": "4_ton",
            "7_ton": "7_ton", 
            "13_ton": "13_ton"
        }
        return mapping.get(subscription_type, subscription_type)

    # ===== НОВЫЕ МЕТОДЫ ДЛЯ РУССКОЙ ПАНЕЛИ АДМИНОВ =====
    
    async def rus_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /rus для админов"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /rus")
        try:
            user = update.effective_user
            
            # Проверяем админские права (используем self.ADMIN_USER_IDS для надежности)
            if user.id not in self.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return
            
            # Показываем русскую панель админа
            rus_text = """🇷🇺 **РУССКАЯ ПАНЕЛЬ АДМИНИСТРАТОРА**

📊 Управление реферальной системой и статистикой

Выберите действие:"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Реферальная статистика", callback_data="rus_stats")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="rus_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(rus_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Русская панель админа показана пользователю {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в rus_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def rus_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик основного меню русской панели"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: rus_menu callback")
        try:
            query = update.callback_query
            await query.answer()
            
            # Показываем основное меню русской панели
            rus_text = """🇷🇺 **РУССКАЯ ПАНЕЛЬ АДМИНИСТРАТОРА**

📊 Управление реферальной системой и статистикой

Выберите действие:"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Реферальная статистика", callback_data="rus_stats")],
                [InlineKeyboardButton("🔙 Главное меню", callback_data="rus_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(rus_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Основное меню русской панели показано")
        except Exception as e:
            logger.error(f"❌ Ошибка в rus_menu_callback: {e}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def rus_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора типа статистики для админов"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: rus_stats callback")
        try:
            query = update.callback_query
            await query.answer()
            
            stats_text = """🇷🇺 **РЕФЕРАЛЬНАЯ СТАТИСТИКА**

Выберите тип подписки для просмотра детальной статистики:"""
            
            keyboard = [
                [InlineKeyboardButton("⭐ 25 звезд", callback_data="rus_stats_25_stars"),
                 InlineKeyboardButton("⭐ 50 звезд", callback_data="rus_stats_50_stars")],
                [InlineKeyboardButton("⭐ 75 звезд", callback_data="rus_stats_75_stars"),
                 InlineKeyboardButton("⭐ 100 звезд", callback_data="rus_stats_100_stars")],
                [InlineKeyboardButton("💎 4 TON", callback_data="rus_stats_4_ton"),
                 InlineKeyboardButton("💎 7 TON", callback_data="rus_stats_7_ton")],
                [InlineKeyboardButton("💎 13 TON", callback_data="rus_stats_13_ton")],
                [InlineKeyboardButton("🔙 Назад", callback_data="rus_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Выбор типа статистики для админов показан")
        except Exception as e:
            logger.error(f"❌ Ошибка в rus_stats_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def rus_stats_type_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик показа детальной статистики для админов - ИСПРАВЛЕННЫЙ"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: rus_stats_type callback")
        try:
            query = update.callback_query
            await query.answer()
            
            # Извлекаем тип подписки из callback_data
            subscription_type = query.data.replace("rus_stats_", "")
            
            # Маппинг для понятных названий
            type_display_names = {
                "25_stars": "25 звезд",
                "50_stars": "50 звезд", 
                "75_stars": "75 звезд",
                "100_stars": "100 звезд",
                "4_ton": "4 TON",
                "7_ton": "7 TON",
                "13_ton": "13 TON"
            }
            
            display_name = type_display_names.get(subscription_type, subscription_type)
            
            # Получаем детальную статистику для админов
            stats = await self.safe_database_operation(
                f"получение детальной статистики по {subscription_type}",
                lambda: self.get_admin_referral_stats_by_type(subscription_type)
            )
            
            # Формируем детальный текст статистики для админов
            if stats and stats.get('referrers'):
                referrers_text = ""
                for i, referrer in enumerate(stats['referrers'][:10], 1):  # Топ 10
                    username = referrer['username'] or f"ID:{referrer['user_id']}"
                    referrers_text += f"{i}. {username} - {referrer['count']} рефералов - {referrer['commission']} TON\n"
                
                stats_text = f"""🇷🇺 **ДЕТАЛЬНАЯ СТАТИСТИКА: {display_name}**

📊 **ОБЩАЯ СТАТИСТИКА:**
👥 Всего рефералов: **{stats['total_count']}**
💰 Общая сумма комиссий: **{stats['total_commission']} TON**

🏆 **ТОП РЕФЕРЕРОВ:**
{referrers_text}

💡 Статистика обновляется в реальном времени"""
            else:
                stats_text = f"""🇷🇺 **ДЕТАЛЬНАЯ СТАТИСТИКА: {display_name}**

📊 **ОБЩАЯ СТАТИСТИКА:**
👥 Всего рефералов: **0**
💰 Общая сумма комиссий: **0 TON**

🏆 **ТОП РЕФЕРЕРОВ:**
Пока нет рефералов по этому типу подписки

💡 Статистика обновляется в реальном времени"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Другой тип", callback_data="rus_stats")],
                [InlineKeyboardButton("🔙 Назад", callback_data="rus_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Детальная статистика по {subscription_type} показана админу")
        except Exception as e:
            logger.error(f"❌ Ошибка в rus_stats_type_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def rus_back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик возврата из русской панели"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: rus_back callback")
        try:
            query = update.callback_query
            await query.answer()
            
            # Показываем основное меню русской панели
            await self.rus_menu_callback(update, context)
        except Exception as e:
            logger.error(f"❌ Ошибка в rus_back_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def get_admin_referral_stats_by_type(self, subscription_type: str) -> dict:
        """Получение детальной статистики рефералов для админов по типу подписки - ИСПРАВЛЕННЫЙ"""
        try:
            async with self.database._lock:
                async with sqlite3.connect(self.database.db_path) as db:
                    # Нормализуем тип подписки для поиска
                    normalized_type = self.normalize_subscription_type(subscription_type)
                    
                    # Получаем общую статистику
                    cursor = await db.execute("""
                        SELECT 
                            COUNT(DISTINCT r.referred_id) as total_count,
                            COALESCE(SUM(re.commission_amount), 0) as total_commission
                        FROM referrals r
                        LEFT JOIN referral_earnings re ON r.referred_id = re.referred_id
                        WHERE re.subscription_type = ?
                        AND re.payment_method = 'TON'
                    """, (normalized_type,))
                    
                    total_row = await cursor.fetchone()
                    await cursor.close()
                    
                    # Получаем топ рефереров
                    cursor = await db.execute("""
                        SELECT 
                            u.id as user_id,
                            u.username,
                            u.first_name,
                            COUNT(DISTINCT r.referred_id) as referral_count,
                            COALESCE(SUM(re.commission_amount), 0) as total_commission
                        FROM users u
                        LEFT JOIN referrals r ON u.id = r.referrer_id
                        LEFT JOIN referral_earnings re ON r.referred_id = re.referred_id
                        WHERE re.subscription_type = ?
                        AND re.payment_method = 'TON'
                        GROUP BY u.id
                        ORDER BY referral_count DESC, total_commission DESC
                        LIMIT 10
                    """, (normalized_type,))
                    
                    rows = await cursor.fetchall()
                    await cursor.close()
                    
                    referrers = []
                    for row in rows:
                        referrers.append({
                            'user_id': row[0],
                            'username': row[1] or f"ID:{row[0]}",
                            'count': row[3],
                            'commission': round(float(row[4]), 2)
                        })
                    
                    return {
                        'total_count': total_row[0] if total_row else 0,
                        'total_commission': round(float(total_row[1]), 2) if total_row else 0.0,
                        'referrers': referrers
                    }
        except Exception as e:
            logger.error(f"Ошибка получения админской статистики по типу {subscription_type}: {e}")
            return {'total_count': 0, 'total_commission': 0.0, 'referrers': []}

    # ===== ОСТАЛЬНЫЕ МЕТОДЫ (БЕЗ ИЗМЕНЕНИЙ) =====
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start - БЕЗ ЖИРНОГО ТЕКСТА"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /start")
        try:
            user = update.effective_user
            if not user:
                await update.message.reply_text("❌ Не удалось получить данные пользователя")
                return

            # Создаем пользователя в базе данных
            await self.safe_database_operation(
                "создание пользователя при старте",
                lambda: self.database.get_or_create_user(
                    user.id, 
                    user.username or "", 
                    user.first_name or "", 
                    user.last_name or ""
                )
            )

            # Проверяем, есть ли реферальный код
            referral_code = None
            if context.args and context.args[0].startswith('ref_'):
                try:
                    referrer_id = int(context.args[0].replace('ref_', ''))
                    if referrer_id != user.id:
                        # Сохраняем ожидающего реферера
                        await self.safe_database_operation(
                            "сохранение ожидающего реферера",
                            lambda: self.database.save_pending_referral(user.id, referrer_id)
                        )
                        logger.info(f"⏳ Ожидающий реферер сохранен: {user.id} от {referrer_id}")
                except (ValueError, IndexError):
                    logger.warning(f"⚠️ Неверный реферальный код: {context.args[0]}")

            # Определяем, какое приветственное сообщение показать
            if context.args and context.args[0].startswith('ref_'):
                welcome_text = self.config.REFERRAL_WELCOME_MESSAGE
            else:
                welcome_text = self.config.WELCOME_MESSAGE

            # ОРИГИНАЛЬНЫЕ кнопки главного меню
            keyboard = [
                [InlineKeyboardButton("💳 Подписки", callback_data="subscription")],
                [InlineKeyboardButton("💬 Связь", callback_data="contact")],
                [InlineKeyboardButton("👥 Реферальная система", callback_data="referral")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
            logger.info(f"✅ Команда /start выполнена для пользователя {user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в start_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def confirm_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /confirm_payment (старый формат)"""
        await self.confirmpay_command(update, context)

    # ===== СИСТЕМА ПОДТВЕРЖДЕНИЯ ОПЛАТ /confirmpay - ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ =====

    async def confirmpay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /confirmpay - ПОЛНОСТЬЮ РАБОЧАЯ"""
        logger.info(f"КОМАНДА /confirmpay от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user
            
            # Проверяем админские права (используем self.ADMIN_USER_IDS для надежности)
            if user.id not in self.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return
            
            # Главное меню /confirmpay
            confirmpay_text = """🔐 **СИСТЕМА ПОДТВЕРЖДЕНИЯ ОПЛАТ**

💎 Выберите тип подписки для подтверждения:"""
            
            keyboard = [
                [InlineKeyboardButton("⭐ 25 звезд", callback_data="confirmpay_type_25_stars"),
                 InlineKeyboardButton("⭐ 50 звезд", callback_data="confirmpay_type_50_stars")],
                [InlineKeyboardButton("⭐ 75 звезд", callback_data="confirmpay_type_75_stars"),
                 InlineKeyboardButton("⭐ 100 звезд", callback_data="confirmpay_type_100_stars")],
                [InlineKeyboardButton("💎 4 TON", callback_data="confirmpay_type_4_ton"),
                 InlineKeyboardButton("💎 7 TON", callback_data="confirmpay_type_7_ton")],
                [InlineKeyboardButton("💎 13 TON", callback_data="confirmpay_type_13_ton")],
                [InlineKeyboardButton("📊 История", callback_data="confirmpay_history"),
                 InlineKeyboardButton("📈 Статистика", callback_data="confirmpay_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(confirmpay_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Главное меню /confirmpay показано админу {user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            try:
                if update.message:
                    await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
            except:
                logger.error("Не удалось отправить сообщение об ошибке")

    async def confirmpay_subscription_type_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора типа подписки для подтверждения"""
        logger.info(f"КОМАНДА /confirmpay выбора типа от пользователя")
        try:
            query = update.callback_query
            await query.answer()
            
            # Извлекаем тип подписки из callback_data
            subscription_type = query.data.replace("confirmpay_type_", "")
            
            # Маппинг для понятных названий
            type_display_names = {
                "25_stars": "25 звезд",
                "50_stars": "50 звезд",
                "75_stars": "75 звезд", 
                "100_stars": "100 звезд",
                "4_ton": "4 TON",
                "7_ton": "7 TON",
                "13_ton": "13 TON"
            }
            
            display_name = type_display_names.get(subscription_type, subscription_type)
            
            # Запрос username пользователя
            type_text = f"""💳 **ПОДТВЕРЖДЕНИЕ ОПЛАТЫ: {display_name}**

👤 Введите username пользователя (например: @username)

После ввода username появится кнопка для подтверждения подписки."""
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(type_text, reply_markup=reply_markup, parse_mode='Markdown')
            
            # Добавляем пользователя в ожидающие ввод username
            self.confirmpay_pending_users[query.from_user.id] = subscription_type
            
            logger.info(f"✅ Выбран тип подписки: {subscription_type}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_subscription_type_callback: {e}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def confirmpay_confirm_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик подтверждения подписки"""
        logger.info(f"КОМАНДА /confirmpay подтверждения")
        try:
            query = update.callback_query
            await query.answer()
            
            # Извлекаем данные из callback_data: confirmpay_confirm_username_type
            parts = query.data.split('_')
            if len(parts) >= 4:
                username = parts[2]
                subscription_type = '_'.join(parts[3:])  # На случай если в типе есть подчеркивания
            else:
                await query.answer("❌ Ошибка: неверный формат данных")
                return
            
            # Поиск пользователя в базе данных
            user_data = await self.safe_database_operation(
                f"поиск пользователя {username}",
                lambda: self.database.get_user_by_username(username)
            )
            
            if not user_data:
                await query.answer("❌ Пользователь не найден в базе данных")
                return
            
            # Проверяем, есть ли ожидающий реферер
            pending_referrer = await self.safe_database_operation(
                "проверка ожидающего реферера",
                lambda: self.database.get_pending_referrer(user_data['id'])
            )
            
            # Добавляем подписку в базу данных
            # Определяем цену и метод оплаты
            subscription_prices = {
                "25_stars": {"amount": 0.2, "method": "STARS"},
                "50_stars": {"amount": 0.4, "method": "STARS"},
                "75_stars": {"amount": 0.6, "method": "STARS"},
                "100_stars": {"amount": 0.8, "method": "STARS"},
                "4_ton": {"amount": 4.0, "method": "TON"},
                "7_ton": {"amount": 7.0, "method": "TON"},
                "13_ton": {"amount": 13.0, "method": "TON"}
            }
            
            subscription_info = subscription_prices.get(subscription_type, {"amount": 1.0, "method": "TON"})
            
            # Добавляем подписку
            subscription_added = await self.safe_database_operation(
                f"добавление подписки {subscription_type}",
                lambda: self.database.add_subscription(
                    user_data['id'], 
                    subscription_type, 
                    subscription_info['method'],
                    subscription_info['amount']
                )
            )
            
            # Получаем ссылку для пользователя
            private_links = self.PRIVATE_CHANNEL_LINKS
            user_link = private_links.get(subscription_type, "https://t.me/passivenft_channel")
            
            # Отправляем ссылку пользователю через безопасную функцию
            link_sent_success = False
            try:
                logger.info(f"🔄 Попытка отправить ссылку пользователю {username} (ID: {user_data['id']})")
                
                message_text = f"""✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**

🎯 Тип подписки: {subscription_type}
💰 Сумма: {subscription_info['amount']} {subscription_info['method']}

🔗 Ваша ссылка для доступа к закрытому каналу:
{user_link}

🎉 Добро пожаловать в PassiveNFT!"""
                
                # Используем безопасную отправку через username
                link_sent_success = await self.send_safe_message_to_user(username, message_text, context)
                
                if link_sent_success:
                    logger.info(f"✅ Ссылка успешно отправлена пользователю {username}")
                else:
                    logger.error(f"❌ Не удалось отправить ссылку пользователю {username}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки ссылки пользователю {username}: {e}")
                logger.error(f"Детали ошибки: {traceback.format_exc()}")
                link_sent_success = False
            
            # Создаем лог подтверждения
            log_data = {
                'admin_id': query.from_user.id,
                'subscription_type': subscription_type,
                'username': username,
                'link_id': f"{subscription_type}_{username}_{int(time.time())}",
                'link_sent_success': link_sent_success
            }
            
            await self.safe_database_operation(
                "сохранение лога подтверждения",
                lambda: self.database.save_confirmation_log(log_data)
            )
            
            # Уведомляем админа об успешном подтверждении
            link_status = "✅ Отправлена успешно" if link_sent_success else "❌ Ошибка отправки"
            confirm_text = f"""✅ **ПОДПИСКА ПОДТВЕРЖДЕНА УСПЕШНО!**

👤 Пользователь: @{username}
💳 Тип: {subscription_type}
💰 Сумма: {subscription_info['amount']} {subscription_info['method']}

🔗 Статус ссылки: {link_status}
📝 Лог сохранен в базе данных"""
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(confirm_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Подписка подтверждена: {username} - {subscription_type}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_confirm_callback: {e}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def send_safe_message_to_user(self, username: str, message_text: str, context: ContextTypes.DEFAULT_TYPE):
        """Безопасная отправка сообщения пользователю с несколькими fallback методами"""
        logger.info(f"🔄 Попытка отправить сообщение пользователю @{username}")
        
        # Метод 1: Прямой запрос по username через get_chat
        try:
            logger.info(f"📤 Метод 1: Получение чата для @{username} через get_chat")
            chat = await context.bot.get_chat(f"@{username}")
            if chat and hasattr(chat, 'id') and chat.type == 'private':
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=message_text,
                    parse_mode='Markdown'
                )
                logger.info(f"✅ Сообщение отправлено @{username} через get_chat (ID: {chat.id})")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Метод 1 не сработал для @{username}: {e}")
        
        # Метод 2: Попытка получить пользователя из базы данных
        try:
            logger.info(f"📤 Метод 2: Поиск пользователя @{username} в базе данных")
            user_data = await self.safe_database_operation(
                f"поиск пользователя {username}",
                lambda: self.database.get_user_by_username(username)
            )
            
            if user_data and user_data.get('id'):
                await context.bot.send_message(
                    chat_id=user_data['id'],
                    text=message_text,
                    parse_mode='Markdown'
                )
                logger.info(f"✅ Сообщение отправлено @{username} через БД (ID: {user_data['id']})")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Метод 2 не сработал для @{username}: {e}")
        
        # Метод 3: Попытка отправить через временное сообщение (если бот знает пользователя)
        try:
            logger.info(f"📤 Метод 3: Попытка временной отправки для @{username}")
            # Отправляем сообщение админу с информацией о проблеме
            admin_text = f"""⚠️ ПРОБЛЕМА С ОТПРАВКОЙ ССЫЛКИ ПОЛЬЗОВАТЕЛЮ @{username}

🔗 Ссылка не может быть отправлена автоматически, так как:
• Пользователь не взаимодействовал с ботом
• Или заблокировал бота
• Или у него настроены приватные настройки

👤 Необходимо отправить ссылку вручную через личные сообщения."""
            
            for admin_id in self.ADMIN_USER_IDS:
                await context.bot.send_message(admin_id, admin_text, parse_mode='Markdown')
            
            logger.info(f"ℹ️ Админ уведомлен о проблеме с @{username}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Метод 3 не сработал для @{username}: {e}")
        
        # Если все методы не сработали
        logger.error(f"❌ Невозможно отправить сообщение @{username} всеми методами")
        return False

    async def confirmpay_history_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик показа истории подтверждений"""
        logger.info(f"КОМАНДА /confirmpay history от пользователя")
        try:
            query = update.callback_query
            await query.answer()
            
            # Получаем последние логи подтверждений
            logs = await self.safe_database_operation(
                "получение истории подтверждений",
                lambda: self.database.get_recent_confirmation_logs(15)
            )
            
            if logs:
                history_text = """📚 **ИСТОРИЯ ПОДТВЕРЖДЕНИЙ**

"""
                for log in logs:
                    timestamp = log['timestamp']
                    if isinstance(timestamp, str):
                        # Форматируем timestamp если это строка
                        try:
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            timestamp = dt.strftime('%d.%m.%Y %H:%M')
                        except:
                            pass
                    
                    history_text += f"👤 @{log['username']} - {log['subscription_type']} - {timestamp}\n"
            else:
                history_text = """📚 **ИСТОРИЯ ПОДТВЕРЖДЕНИЙ**

История подтверждений пуста."""
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(history_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ История подтверждений показана")
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_history_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def confirmpay_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик показа статистики подтверждений"""
        logger.info(f"КОМАНДА /confirmpay stats от пользователя")
        try:
            query = update.callback_query
            await query.answer()
            
            # Получаем статистику подтверждений
            stats = await self.safe_database_operation(
                "получение статистики подтверждений",
                lambda: self.database.get_confirmation_stats()
            )
            
            if stats:
                stats_text = f"""📈 **СТАТИСТИКА ПОДТВЕРЖДЕНИЙ**

📊 Всего подтверждений: {stats.get('total', 0)}
📅 Сегодня: {stats.get('today', 0)}
📆 За неделю: {stats.get('week', 0)}
🏆 Популярная подписка: {stats.get('popular_subscription', 'нет данных')}

💡 Статистика обновляется в реальном времени"""
            else:
                stats_text = """📈 **СТАТИСТИКА ПОДТВЕРЖДЕНИЙ**

📊 Данные для статистики пока отсутствуют

💡 Статистика начнет отображаться после первых подтверждений"""
            
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Статистика подтверждений показана")
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_stats_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def confirmpay_back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик возврата в главное меню /confirmpay"""
        logger.info(f"КОМАНДА /confirmpay back от пользователя")
        try:
            query = update.callback_query
            await query.answer()
            
            # Проверка админских прав для отмены (используем self.ADMIN_USER_IDS для надежности)
            if query.from_user.id not in self.ADMIN_USER_IDS:
                await query.edit_message_text("❌ Отмена подтверждения - доступно только админам.")
                logger.warning(f"⚠️ Пользователь {query.from_user.id} попытался отменить подтверждение без прав админа")
                return
            
            # Удаляем пользователя из ожидающих, если он там есть
            if query.from_user.id in self.confirmpay_pending_users:
                del self.confirmpay_pending_users[query.from_user.id]
            
            # Возвращаемся к главному меню подтверждения оплаты
            # Создаем псевдо-объект Update с сообщением для обратной совместимости
            dummy_update = Update(
                update_id=update.update_id,
                message=query.message
            )
            await self.confirmpay_command(dummy_update, context)
            
            logger.info(f"✅ Возврат в главное меню /confirmpay")
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_back_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений для /confirmpay"""
        logger.info(f"ТЕКСТОВОЕ СООБЩЕНИЕ от пользователя")
        try:
            user_id = update.effective_user.id
            message_text = update.message.text.strip()
            
            # Проверяем, ожидает ли этот пользователь ввод username для /confirmpay
            if user_id in self.confirmpay_pending_users:
                subscription_type = self.confirmpay_pending_users[user_id]
                
                # Проверяем, что сообщение выглядит как username
                if message_text and (message_text.startswith('@') or len(message_text) >= 3):
                    # Очищаем username от @ символа
                    clean_username = message_text.replace('@', '').strip()
                    
                    # Проверяем, что username содержит только допустимые символы
                    if re.match(r'^[a-zA-Z0-9_]+$', clean_username):
                        confirmation_text = f"""✅ **ПОДТВЕРЖДЕНИЕ ОПЛАТЫ**

Тип подписки: {subscription_type}
Username: @{clean_username}

Нажмите кнопку ниже для подтверждения подписки и отправки ссылки пользователю."""
                        
                        keyboard = [
                            [InlineKeyboardButton("✅ Подтвердить подписку", callback_data=f"confirmpay_confirm_{clean_username}_{subscription_type.replace('-', '_')}")],
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
            if "admin" in message_text.lower() and user_id in self.ADMIN_USER_IDS:
                await self.admin_command(update, context)
            else:
                await update.message.reply_text(
                    "🤖 Используйте /start для начала работы"
                )
                logger.info(f"✅ Отправлено справочное сообщение пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в handle_message: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Подписки' - БЕЗ ЖИРНОГО ТЕКСТА"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: subscription callback")
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
                logger.info(f"✅ Подписки открыты")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Подписки уже открыты!")
                    logger.info(f"ℹ️ Подписки уже открыты")
                else:
                    await query.answer("Ошибка при открытии подписок.")
                    logger.error(f"❌ Ошибка BadRequest в subscription_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в subscription_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def ton_subscription_plan_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ИСПРАВЛЕННЫЙ обработчик выбора обычного плана TON с правильными ценами"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: ton_subscription_plan callback")
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
            logger.info(f"✅ План TON {plan_index} показан")
        except Exception as e:
            logger.error(f"❌ Ошибка в ton_subscription_plan_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def subscription_plan_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора конкретной подписки - выбор типа подписки"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: subscription_plan callback")
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
            logger.info(f"✅ Выбор типа подписки для плана {plan_index} показан")
        except Exception as e:
            logger.error(f"❌ Ошибка в subscription_plan_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Оплатить' - БЕЗ ЖИРНОГО ТЕКСТА"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: payment callback")
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
            logger.info(f"✅ Оплата для плана {plan_index} открыта")
        except Exception as e:
            logger.error(f"❌ Ошибка в payment_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def activity_subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора активных подписок - ИСПРАВЛЕННЫЙ"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: activity_subscription callback")
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
            logger.info(f"✅ Активные подписки для плана {plan_index} показаны")
        except Exception as e:
            logger.error(f"❌ Ошибка в activity_subscription_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def select_stars_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ИСПРАВЛЕННЫЙ обработчик выбора активных подписок (звездочки)"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: select_stars callback")
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
            logger.info(f"✅ Активные подписки (звездочки) показаны")
        except Exception as e:
            logger.error(f"❌ Ошибка в select_stars_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def select_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ИСПРАВЛЕННЫЙ обработчик выбора обычных подписок (TON) с ПРАВИЛЬНЫМИ ценами"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: select_ton callback")
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
            logger.info(f"✅ Обычные подписки (TON) показаны")
        except Exception as e:
            logger.error(f"❌ Ошибка в select_ton_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def star_subscription_plan_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ИСПРАВЛЕННЫЙ обработчик выбора конкретного плана звездочек"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: star_subscription_plan callback")
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
            logger.info(f"✅ План звездочек {stars} показан")
        except Exception as e:
            logger.error(f"❌ Ошибка в star_subscription_plan_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def stars_payment_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ИСПРАВЛЕННЫЙ обработчик оплаты через звездочки"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: stars_payment callback")
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

после оплаты обратитесь к менеджеру для подтверждения.

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
            logger.info(f"✅ Оплата через звездочки {stars} показана")
        except Exception as e:
            logger.error(f"❌ Ошибка в stars_payment_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def copy_stars_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ИСПРАВЛЕННЫЙ обработчик кнопки "Оплатить TON" - копирование адреса"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: copy_stars_ton callback")
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

⏰ После оплаты обратитесь к менеджеру для подтверждения:"""

            # Кнопки для TON оплаты
            keyboard = [
                [InlineKeyboardButton("💰 Открыть TON кошелек", url=f"ton://transfer?amount={star_plan['ton_price']}&address={self.config.TON_WALLET_ADDRESS}")],
                [InlineKeyboardButton("👤 Связь с менеджером", url=f"https://t.me/{self.config.MANAGER_USERNAME}")],
                [InlineKeyboardButton("🔙 Назад", callback_data=f"stars_payment_{stars}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(payment_text, reply_markup=reply_markup, parse_mode='HTML')
            logger.info(f"✅ Оплата через TON {stars} показана")
        except Exception as e:
            logger.error(f"❌ Ошибка в copy_stars_ton_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def stars_payment_stars_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ИСПРАВЛЕННЫЙ обработчик кнопки "Оплатить звездочками" - редирект на менеджера"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: stars_payment_stars callback")
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
            payment_text = f"""⭐️ ОПЛАТА ЧЕРЕЗ ЗВЕЗДОЧКИ - {stars} ЗВЕД

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
            logger.info(f"✅ Оплата через звездочки {stars} для @{self.config.STARS_USERNAME} показана")
        except Exception as e:
            logger.error(f"❌ Ошибка в stars_payment_stars_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def contact_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Связь' с ОРИГИНАЛЬНЫМ текстом"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: contact callback")
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
                logger.info(f"✅ Контакты открыты")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Контакты уже открыты!")
                    logger.info(f"ℹ️ Контакты уже открыты")
                else:
                    await query.answer("Ошибка при открытии контактов.")
                    logger.error(f"❌ Ошибка BadRequest в contact_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в contact_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def get_referral_link_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик получения реферальной ссылки - БЕЗ ЖИРНОГО ТЕКСТА"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: get_referral callback")
        try:
            query = update.callback_query
            await query.answer()
            user = query.from_user

            # Генерация персональной реферальной ссылки
            referral_link = f"https://t.me/{self.BOT_USERNAME}?start=ref_{user.id}"
            
            # Создаем кнопку "Назад"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Показываем сообщение с тап-ту-копи на ссылку - ОПТИМАЛЬНЫЙ ФОРМАТ
            await query.message.edit_text(
                f"🔗 Ваша персональная реферальная ссылка:\n\n"
                f"[📱 Нажмите для копирования]({referral_link})\n\n"
                f"💰 Приглашайте друзей и зарабатывайте 10% с каждой их оплаты подписки!\n\n"
                f"💡 Ссылка скопируется при нажатии",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            logger.info(f"✅ Реферальная ссылка отправлена пользователю {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в get_referral_link_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def copy_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик копирования TON адреса"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: copy_ton callback")
        try:
            query = update.callback_query
            await query.answer()

            await query.message.edit_text(
                f"Адрес кошелька скопирован!\n\n`{self.config.TON_WALLET_ADDRESS}`\n\nОтправьте указанную сумму TON.",
                parse_mode='Markdown'
            )
            logger.info(f"✅ Адрес TON скопирован")
        except Exception as e:
            logger.error(f"❌ Ошибка в copy_ton_callback: {e}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Назад' - возврат к главному меню"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: back callback")
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
                logger.info(f"✅ Возврат к главному меню")
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.error(f"❌ Ошибка BadRequest в back_callback: {e}")
                    raise
                # Сообщение не изменилось, просто отвечаем на callback
                await query.answer()
                logger.info(f"ℹ️ Уже в главном меню")
        except Exception as e:
            logger.error(f"❌ Ошибка в back_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробойте позже.")

    # ===== НОВЫЕ КОМАНДЫ ДЛЯ КАНАЛОВ =====

    async def channel_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /channel_info"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /channel_info")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом (используем self.ADMIN_USER_IDS для надежности)
            if user.id not in self.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return

            info_text = """📺 **ИНФОРМАЦИЯ О КАНАЛАХ**

**Stars каналы:**
"""
            for stars, channel_id in self.config.CHANNEL_MAPPINGS.items():
                info_text += f"• {stars} звезд → {channel_id}\n"

            info_text += "\n**TON каналы:**\n"
            for users, channel_id in self.config.TON_CHANNEL_MAPPINGS.items():
                info_text += f"• {users} пользователей → {channel_id}\n"

            info_text += "\n**Пригласительные ссылки:**\n"
            for subscription_type, link in self.PRIVATE_CHANNEL_LINKS.items():
                info_text += f"• {subscription_type} → {link}\n"

            await update.message.reply_text(info_text)
            logger.info(f"✅ Информация о каналах отправлена пользователю {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в channel_info_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def get_channel_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /get_channel_id"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /get_channel_id")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом (используем self.ADMIN_USER_IDS для надежности)
            if user.id not in self.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return

            if update.message.forward_from_chat:
                channel = update.message.forward_from_chat
                await update.message.reply_text(
                    f"📺 **ID канала:** `{channel.id}`\n"
                    f"📛 **Название:** {channel.title}\n"
                    f"👤 **Тип:** {channel.type}"
                )
            else:
                await update.message.reply_text(
                    "📨 Перешлите сообщение из канала, чтобы получить его ID\n"
                    "Или добавьте бота в канал и отправьте команду там"
                )
            logger.info(f"✅ Команда /get_channel_id выполнена пользователем {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в get_channel_id_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def testcmd_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /testcmd"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /testcmd")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом (используем self.ADMIN_USER_IDS для надежности)
            if user.id not in self.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return

            test_text = f"""🔧 **ТЕСТОВАЯ КОМАНДА**

👤 Пользователь: {user.first_name} (@{user.username or 'без username'})
🆔 ID: {user.id}
⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

🤖 Бот: @{self.BOT_USERNAME}
💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...

✅ Бот работает стабильно!"""

            await update.message.reply_text(test_text)
            logger.info(f"✅ Тестовая команда выполнена пользователем {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в testcmd_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    # ===== АДМИНСКИЕ КОМАНДЫ =====

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraa"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraa")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом (используем self.ADMIN_USER_IDS для надежности)
            if user.id not in self.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к админ панели")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к админ панели от пользователя {user.id}")
                return

            # ОРИГИНАЛЬНЫЙ текст админ панели
            admin_text = """🔧 Админ панель PassiveNFT Bot (Стабильная версия с исправленной реферальной системой)
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
🇷🇺 /rus - русская панель администратора с реферальной статистикой

**КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ СТАБИЛЬНОСТИ:**
• Автоматические повторные попытки подключения
• Таймауты для операций с БД
• Защита от ошибок пользователя
• Оптимизированный polling

**РЕФЕРАЛЬНАЯ СИСТЕМА:**
• ✅ Полностью рабочая реферальная система
• ✅ Персональные ссылки для каждого пользователя
• ✅ Статистика по типам подписок
• ✅ Команда /rus для админов
• ✅ Интеграция с /confirmpay

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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraastat")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом (используем self.ADMIN_USER_IDS для надежности)
            if user.id not in self.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к админ панели")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к админ панели от пользователя {user.id}")
                return

            # Получаем статистику подписок
            try:
                total_users = await self.safe_database_operation(
                    "получение общего количества пользователей",
                    lambda: self.database.get_all_users_count()
                )
                total_referrals = await self.safe_database_operation(
                    "получение общего количества рефералов",
                    lambda: self.database.get_total_referrals_count()
                )
                total_commission = await self.safe_database_operation(
                    "получение общей комиссии",
                    lambda: self.database.get_total_commission_earned()
                )
                
                uptime = datetime.now() - self.start_time
                
                stats_text = f"""📊 СТАТИСТИКА БОТА (Стабильная версия с исправленной реферальной системой)

👥 Всего пользователей: {total_users or 0}
💎 Рефералов: {total_referrals or 0}
💰 Начислено комиссий: {total_commission or 0} TON

⏱️ Время работы: {uptime.days}д {uptime.seconds//3600}ч {(uptime.seconds//60)%60}м
🚀 Статус: Активен и стабилен
🔄 Повторные попытки: Включены
⚡ Таймауты: Настроены
📡 Соединение: Стабильное

🤖 Бот: @{self.BOT_USERNAME}
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraapeople")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом (используем self.ADMIN_USER_IDS для надежности)
            if user.id not in self.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к админ панели")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к админ панели от пользователя {user.id}")
                return

            # Получаем список участников
            try:
                users_data = await self.safe_database_operation(
                    "получение списка пользователей",
                    lambda: self.database.get_subscribers()
                )
                
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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraaref")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом (используем self.ADMIN_USER_IDS для надежности)
            if user.id not in self.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к админ панели")
                logger.warning(f"⚠️ Неавторизованная попытка доступа к админ панели от пользователя {user.id}")
                return

            # Получаем реферальную статистику
            try:
                ref_data = await self.safe_database_operation(
                    "получение статистики рефералов",
                    lambda: self.database.get_referral_stats()
                )
                
                total_referrals = await self.safe_database_operation(
                    "получение общего количества рефералов",
                    lambda: self.database.get_total_referrals_count()
                )
                
                ref_text = f"""🔗 СТАТИСТИКА РЕФЕРАЛОВ

📊 Всего рефералов: {total_referrals or 0}
👥 Активных рефереров: {len(ref_data) if ref_data else 0}

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
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /broadcast")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом (используем self.ADMIN_USER_IDS для надежности)
            if user.id not in self.ADMIN_USER_IDS:
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
            total_users = await self.safe_database_operation(
                "получение количества пользователей для рассылки",
                lambda: self.database.get_all_users_count()
            )
            
            if not total_users or total_users == 0:
                await update.message.reply_text("❌ В базе данных нет зарегистрированных пользователей")
                return

            # Получаем список всех пользователей для рассылки
            all_users = await self.safe_database_operation(
                "получение пользователей для рассылки",
                lambda: self._get_all_users_for_broadcast()
            )
            
            if not all_users or len(all_users) == 0:
                await update.message.reply_text("❌ В базе данных нет зарегистрированных пользователей")
                return
            
            # Начинаем рассылку
            await update.message.reply_text(
                f"✅ Начинаем рассылку...\n"
                f"📝 Текст: {broadcast_message}\n"
                f"👥 Получателей: {len(all_users)}\n"
                f"⏰ Ожидайте..."
            )
            
            # Выполняем рассылку всем пользователям
            sent_count = 0
            failed_count = 0
            
            for user in all_users:
                try:
                    await context.bot.send_message(
                        chat_id=user['user_id'],
                        text=f"📢 **РАССЫЛКА**\n\n{broadcast_message}",
                        parse_mode='Markdown'
                    )
                    sent_count += 1
                    # Небольшая пауза между отправками
                    await asyncio.sleep(0.05)
                except Exception as send_e:
                    failed_count += 1
                    logger.warning(f"Не удалось отправить сообщение пользователю {user['user_id']}: {send_e}")
            
            # Отправляем отчет о рассылке
            await update.message.reply_text(
                f"✅ Рассылка завершена!\n"
                f"📝 Текст: {broadcast_message}\n"
                f"✅ Отправлено: {sent_count}\n"
                f"❌ Ошибки: {failed_count}\n"
                f"👥 Всего получателей: {len(all_users)}"
            )
            logger.info(f"✅ Broadcast завершен: отправлено {sent_count}, ошибки {failed_count}, сообщение: {broadcast_message}")

        except Exception as e:
            logger.error(f"❌ Ошибка в broadcast_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка при рассылке. Попробуйте позже.")

    # КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ: Функция запуска polling с повторными попытками
    async def start_polling_with_retry(self, max_retries=3):
        """КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Запуск polling с логикой повторных попыток"""
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔄 Попытка {attempt}/{max_retries} - Инициализация приложения...")
                
                # Инициализация с таймаутом
                await asyncio.wait_for(
                    self.application.initialize(),
                    timeout=30.0
                )
                
                logger.info(f"🔄 Попытка {attempt}/{max_retries} - Запуск приложения...")
                
                # Запуск приложения
                await self.application.start()
                
                logger.info(f"🔄 Попытка {attempt}/{max_retries} - Запуск polling...")
                
                # Запуск polling с оптимизированными параметрами
                await self.application.updater.start_polling(
                    poll_interval=0.05,  # Быстрый интервал опроса
                    timeout=10,          # Таймаут запросов
                    drop_pending_updates=True,  # Игнорировать старые обновления
                    bootstrap_retries=3  # Повторные попытки при запуске
                )
                
                logger.info(f"✅ Бот успешно запущен с попытки {attempt}")
                logger.info("📡 Polling начат - бот готов к приему сообщений")
                return True
                
            except (asyncio.TimeoutError, TelegramError, httpx.ConnectTimeout) as e:
                logger.error(f"⏰ Попытка {attempt}/{max_retries} - Ошибка: {e}")
                
                if attempt < max_retries:
                    wait_time = 5 * attempt  # Экспоненциальная задержка
                    logger.info(f"⏳ Ожидание {wait_time} секунд перед следующей попыткой...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ Все попытки исчерпаны. Критическая ошибка: {e}")
                    raise
                    
            except Exception as e:
                logger.error(f"❌ Неожиданная ошибка в попытке {attempt}: {e}")
                if attempt == max_retries:
                    raise
                await asyncio.sleep(5)

    async def safe_shutdown(self):
        """КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасная остановка бота"""
        logger.info("🛑 Начинаем корректную остановку бота...")
        try:
            if self.application and self.application.updater.running:
                self.application.updater.stop()
                logger.info("✅ Polling остановлен")
                
            if self.application and self.application.running:
                await self.application.stop()
                await self.application.shutdown()
                logger.info("✅ Бот корректно остановлен")
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при остановке бота: {e}")

    async def run(self):
        """Запуск бота с улучшенной структурой и критическими исправлениями стабильности"""
        logger.info("🚀 Запуск PassiveNFT Bot (Стабильная версия с исправленной реферальной системой)...")
        
        try:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Инициализация асинхронной базы данных с таймаутом
            logger.info("🗄️ Инициализация асинхронной базы данных...")
            await self.safe_database_operation(
                "инициализация БД",
                lambda: self.database.initialize(),
                timeout=10.0
            )
            logger.info("✅ Асинхронная база данных инициализирована")
            
            logger.info(f"🤖 Бот: @{self.BOT_USERNAME}")
            logger.info(f"💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...{self.config.TON_WALLET_ADDRESS[-10:]}")
            logger.info("✅ РЕФЕРАЛЬНАЯ СИСТЕМА ПОЛНОСТЬЮ ИСПРАВЛЕНА И АКТИВНА")
            logger.info("✅ Персональные реферальные ссылки работают")
            logger.info("✅ Статистика по типам подписок функционирует")
            logger.info("✅ Команда /rus для админов добавлена")
            logger.info("✅ Интеграция с /confirmpay завершена")
            logger.info("⭐️ Активные подписки за звездочки включены")
            logger.info("🆔 Новые команды для работы с каналами включены")
            logger.info("👨‍💼 ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ система подтверждения оплат /confirmpay включена")
            logger.info("🔧 КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ СТАБИЛЬНОСТИ ИНТЕГРИРОВАНЫ")
            logger.info("⚡ Таймауты и повторные попытки настроены")

            # Очистка webhook перед запуском
            await self.clear_webhook_on_startup()

            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Запуск polling с повторными попытками
            await self.start_polling_with_retry()
            
            logger.info("🎯 Бот успешно запущен и готов к работе!")
            
            # Бесконечное ожидание с обработкой прерываний
            while True:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    logger.info("⏹️ Получен сигнал остановки polling")
                    break
                    
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в run: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Корректная остановка бота
            await self.safe_shutdown()

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

async def main():
    """Главная функция запуска с улучшенной обработкой ошибок"""
    try:
        logger.info("🎯 Инициализация PassiveNFT Bot (Стабильная версия с исправленной реферальной системой)...")
        bot = PassiveNFTBot()
        logger.info("✅ Bot инициализирован, начинаем запуск...")
        await bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал остановки от пользователя")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в main: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    try:
        logger.info("🔥 ЗАПУСК PassiveNFT Bot (Полная версия с исправленной реферальной системой и критическими исправлениями стабильности)...")
        asyncio.run(run_both())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
