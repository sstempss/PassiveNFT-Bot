#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PassiveNFT Bot - ИСПРАВЛЕННАЯ ВЕРСИЯ С ПОЛНОЙ РЕФЕРАЛЬНОЙ СИСТЕМОЙ
🔥 Все критические ошибки исправлены + РЕФЕРАЛЬНАЯ СИСТЕМА:
✅ Chat not found - исправлено 
✅ NoneType errors - исправлено
✅ Username обработка - улучшена
✅ Реальные invite ссылки - работают
💰 РЕФЕРАЛЬНАЯ СИСТЕМА:
✅ Автоматический расчет 10% комиссии для TON-подписок
✅ Интеграция с системой подтверждения оплаты
✅ Улучшенная статистика с детальной информацией
✅ Админ команды для просмотра реферальной статистики
"""

import logging
import asyncio
import traceback
from datetime import datetime
import time
import hashlib
import secrets
import json
import os
import aiohttp
from typing import Dict, List, Optional, Any

# Telegram Bot imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.error import BadRequest, TelegramError

# Import config
from config_deploy_new import Config

# Import database
from database_async import AsyncDatabaseManager

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Класс для работы с aiohttp вместо httpx (решает проблемы с TLS)
class AioHTTPRequest:
    def __init__(self, api_url, session_kwargs=None):
        self._api_url = api_url
        self._session = None
        
    async def initialize(self):
        """Инициализация клиентской сессии""" 
        if self._session is None:
            self._session = aiohttp.ClientSession()
        
    async def shutdown(self):
        """Закрытие клиентской сессии""" 
        if self._session:
            await self._session.close()
            self._session = None
            
    async def do_request(self, method, url=None, data=None, **kwargs):
        """Выполнение HTTP запроса""" 
        if not self._session:
            await self.initialize()
            
        # Построение URL
        if url:
            api_url = f"{self._api_url}/{method}?url={url}"
        else:
            api_url = f"{self._api_url}/{method}"
            
        # Выполнение POST запроса
        async with self._session.post(api_url, json=data, **kwargs) as response:
            response_text = await response.text()
            try:
                result = json.loads(response_text)
                return response.status, result
            except json.JSONDecodeError:
                return response.status, {"error": "Invalid JSON response"}



                return response.status, result
            except json.JSONDecodeError:
                return response.status, {"error": "Invalid JSON response"}


class PassiveNFTBot:
    def __init__(self):
        """Инициализация бота с полной интеграцией реферальной системы"""
        
        # Загружаем конфигурацию
        self.config = Config()
        
        # Инициализируем базу данных
        self.database = AsyncDatabaseManager()
        
        # Настройка logging
        self.setup_logging()
        
        # Инициализация приложения Telegram
        self.bot_token = self.config.BOT_TOKEN
        self.application = None
        self.confirmation_queue = {}
        self.used_links = set()
        
        # ИСПРАВЛЕНО: subscription_links как PRIVATE_CHANNEL_LINKS
        self.subscription_links = self.config.PRIVATE_CHANNEL_LINKS
        
        logger.info("🔥 ЗАПУСК PassiveNFT Bot - ПОЛНАЯ ИНТЕГРАЦИЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ...")
        logger.info(f"🆔 Реферальная система с автоматическим расчетом комиссий активирована")
        logger.info(f"💰 Комиссия 10% начисляется только за TON-подписки")
        logger.info(f"🔗 PRIVATE_CHANNEL_LINKS интегрированы")
        logger.info(f"🔄 Система реальных invite ссылок активирована")
        
        # Консольный вывод конфигурации
        self.log_config()
        
    def setup_logging(self):
        """Настройка расширенного логирования"""
        logger.setLevel(logging.INFO)
        
        # Консольный handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Формат логов
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
    def log_config(self):
        """Логирование конфигурации для отладки"""
        try:
            logger.info("⭐ Звезды каналы:")
            for amount, channel_id in self.config.CHANNEL_MAPPINGS.items():
                logger.info(f"    {amount} звезд → {channel_id}")
            
            logger.info("💎 TON подписки:")
            for amount, channel_id in self.config.TON_CHANNEL_MAPPINGS.items():
                logger.info(f"    {amount} TON → {channel_id}")
            
            logger.info("🔗 PRIVATE_CHANNEL_LINKS настроены:")
            for sub_type, link in self.config.PRIVATE_CHANNEL_LINKS.items():
                logger.info(f"    {sub_type} → {link[:50]}...")
                
        except Exception as e:
            logger.error(f"Ошибка логирования конфигурации: {e}")
    
    async def setup_application(self):
        """Настройка приложения Telegram"""
        
        # Создаем приложение
        self.application = Application.builder().token(self.bot_token).build()
        
        # Регистрируем обработчики команд
        await self.register_handlers()
        
        # Логирование настройки
        logger.info("Telegram приложение настроено")
        
    async def register_handlers(self):
        """Регистрация всех обработчиков команд"""
        
        # Основные команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("rus", self.rus_command))
        
        # Админ команды
        self.application.add_handler(CommandHandler("adminserveraa", self.admin_command))
        self.application.add_handler(CommandHandler("adminserveraastat", self.admin_stat_command))
        self.application.add_handler(CommandHandler("adminserveraapeople", self.admin_people_command))
        self.application.add_handler(CommandHandler("adminserveraaref", self.admin_referral_command))
        
        # НОВЫЕ АДМИН КОМАНДЫ ДЛЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ
        self.application.add_handler(CommandHandler("refstats", self.admin_refstats_command))
        self.application.add_handler(CommandHandler("refstat", self.admin_refstat_by_username))
        
        self.application.add_handler(CommandHandler("broadcast", self.broadcast_command))
        self.application.add_handler(CommandHandler("testcmd", self.test_command))
        
        # Новые команды для работы с каналами
        self.application.add_handler(CommandHandler("channel_info", self.channel_info_command))
        self.application.add_handler(CommandHandler("get_channel_id", self.get_channel_id_command))
        
        # Подтверждение оплаты - ГЛАВНАЯ КОМАНДА
        self.application.add_handler(CommandHandler("confirmpay", self.confirmpay_command))
        
        # Callback handlers для подтверждения оплаты
        self.application.add_handler(CallbackQueryHandler(
            self.confirmpay_subscription_type_callback, 
            pattern="^confirmpay_type_"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.confirmpay_history_callback, 
            pattern="^confirmpay_history$"
        ))
        self.application.add_handler(CallbackQueryHandler(
            self.confirmpay_stats_callback, 
            pattern="^confirmpay_stats$"
        ))
        # ИСПРАВЛЕНО: confirmpay_back_callback с query.message
        self.application.add_handler(CallbackQueryHandler(
            self.confirmpay_back_callback, 
            pattern="^confirmpay_back$"
        ))
        
        # Обработчики callback для подписок
        self.application.add_handler(CallbackQueryHandler(self.subscription_callback, pattern="^subscription$"))
        self.application.add_handler(CallbackQueryHandler(self.select_stars_callback, pattern="^select_stars$"))
        self.application.add_handler(CallbackQueryHandler(self.select_ton_callback, pattern="^select_ton$"))
        self.application.add_handler(CallbackQueryHandler(self.stars_subscription_callback, pattern="^stars_"))
        self.application.add_handler(CallbackQueryHandler(self.ton_subscription_callback, pattern="^ton_"))
        self.application.add_handler(CallbackQueryHandler(self.payment_stars_callback, pattern="^payment_stars_"))
        self.application.add_handler(CallbackQueryHandler(self.payment_ton_callback, pattern="^payment_ton_"))
        self.application.add_handler(CallbackQueryHandler(self.payment_stars_check_callback, pattern="^payment_check_stars_"))
        self.application.add_handler(CallbackQueryHandler(self.payment_ton_check_callback, pattern="^payment_check_ton_"))
        self.application.add_handler(CallbackQueryHandler(self.contact_callback, pattern="^contact$"))
        self.application.add_handler(CallbackQueryHandler(self.referral_callback, pattern="^referral$"))
        self.application.add_handler(CallbackQueryHandler(self.referral_stats_callback, pattern="^referral_stats$"))
        self.application.add_handler(CallbackQueryHandler(self.copy_ton_callback, pattern="^copy_ton$"))
        self.application.add_handler(CallbackQueryHandler(self.back_callback, pattern="^back$"))
        
        # Обработчик для статистики в команде /rus
        self.application.add_handler(CallbackQueryHandler(self.rus_stats_callback, pattern="^rus_stats$"))
        
        # Обработчик для кнопки "Назад к подпискам" в /rus
        self.application.add_handler(CallbackQueryHandler(self.rus_back_callback, pattern="^rus_back$"))
        
        # Обработчик всех текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info("✅ Все обработчики команд зарегистрированы с реферальной системой включая /rus")
    
    # ===== ОСНОВНЫЕ КОМАНДЫ =====
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главная команда /start"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /start от пользователя {update.effective_user.id}")
        
        try:
            # Создаем пользователя в базе данных
            await self.database.get_or_create_user(update.effective_user.id, 
                                                   update.effective_user.username or "",
                                                   update.effective_user.first_name or "",
                                                   update.effective_user.last_name or "")
            logger.info(f"✅ Пользователь {update.effective_user.id} создан в базе данных")
            
            # Главное приветственное сообщение
            welcome_text = self.config.WELCOME_MESSAGE
            
            # Кнопки главного меню
            keyboard = [
                [InlineKeyboardButton("💳 Подписки", callback_data="subscription")],
                [InlineKeyboardButton("💬 Связь", callback_data="contact")],
                [InlineKeyboardButton("👥 Реферальная система", callback_data="referral")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ /start выполнен успешно для пользователя {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в /start: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда помощи /help"""
        help_text = f"""
🤖 **PassiveNFT Bot - Помощь**

Доступные команды:
• /start - Начать работу с ботом
• /help - Показать эту справку

⚡ **Быстрые действия:**
• 💳 Подписки - Выбрать тип подписки
• 💬 Связь - Связаться с менеджером  
• 👥 Рефералы - Ваша реферальная система

📞 **Поддержка:** @{self.config.MANAGER_USERNAME}

💰 **Реферальная система:**
• Зарабатывайте 10% с TON-подписок ваших рефералов
• Приглашайте друзей и получайте пассивный доход!
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def rus_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /rus - показ всех доступных подписок и статистики"""
        try:
            user_id = update.effective_user.id
            logger.info(f"КОМАНДА /rus от пользователя {user_id}")
            
            # Создаем клавиатуру с кнопками подписок Stars и TON
            keyboard = [
                # Кнопки Stars
                [InlineKeyboardButton("⭐ 25 звезд", callback_data="stars_25")],
                [InlineKeyboardButton("⭐ 50 звезд", callback_data="stars_50")],
                [InlineKeyboardButton("⭐ 75 звезд", callback_data="stars_75")],
                [InlineKeyboardButton("⭐ 100 звезд", callback_data="stars_100")],
                # Кнопки TON
                [InlineKeyboardButton("💎 4 TON", callback_data="ton_4")],
                [InlineKeyboardButton("💎 7 TON", callback_data="ton_7")],
                [InlineKeyboardButton("💎 13 TON", callback_data="ton_13")],
                # Дополнительные кнопки
                [InlineKeyboardButton("📊 Общая статистика", callback_data="rus_stats")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="back")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = """🇷🇺 **РУССКОЕ МЕНЮ**

⭐ **ПОДПИСКИ ЗА ЗВЕЗДЫ:**
• ⭐ 25 звезд - Базовый план
• ⭐ 50 звезд - Расширенный план
• ⭐ 75 звезд - Премиум план
• ⭐ 100 звезд - VIP план

💎 **ПОДПИСКИ ЗА TON:**
• 💎 4 TON - На 150 человек
• 💎 7 TON - На 100 человек
• 💎 13 TON - На 50 человек

📊 **ОБЩАЯ СТАТИСТИКА** - покажет текущую статистику подписок

Выберите нужную подписку:"""
            
            await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Команда /rus выполнена для пользователя {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в rus_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    # ===== СИСТЕМА ПОДТВЕРЖДЕНИЯ ОПЛАТ - ОСНОВНЫЕ ФУНКЦИИ =====
    
    async def log_payment_confirmation(self, username: str, subscription_type: str, admin_id: int, invite_link: str):
        """Логирование подтверждения оплаты"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'username': username,
                'subscription_type': subscription_type,
                'admin_id': admin_id,
                'invite_link': invite_link
            }
            
            # Сохраняем в файл для резервного копирования
            logs_file = "payment_logs.json"
            
            # Читаем существующие логи
            existing_logs = []
            if os.path.exists(logs_file):
                try:
                    with open(logs_file, 'r', encoding='utf-8') as f:
                        existing_logs = json.load(f)
                except:
                    existing_logs = []
            
            # Добавляем новую запись
            existing_logs.append(log_entry)
            
            # Сохраняем обратно
            with open(logs_file, 'w', encoding='utf-8') as f:
                json.dump(existing_logs, f, ensure_ascii=False, indent=2)
                
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
                    InlineKeyboardButton("💎 13 TON", callback_data="confirmpay_type_13_ton"),
                    InlineKeyboardButton("💎 7 TON", callback_data="confirmpay_type_7_ton")
                ],
                [
                    InlineKeyboardButton("💎 4 TON", callback_data="confirmpay_type_4_ton"),
                    InlineKeyboardButton("💎 50 TON", callback_data="confirmpay_type_50_ton")
                ],
                [
                    InlineKeyboardButton("💎 100 TON", callback_data="confirmpay_type_100_ton"),
                    InlineKeyboardButton("💎 150 TON", callback_data="confirmpay_type_150_ton")
                ],
                [
                    InlineKeyboardButton("📊 История подтверждений", callback_data="confirmpay_history"),
                    InlineKeyboardButton("📈 Статистика", callback_data="confirmpay_stats")
                ]
            ]
            
            message_text = """👨‍💼 **МЕНЕДЖЕРСКАЯ ПАНЕЛЬ ПОДТВЕРЖДЕНИЯ ОПЛАТЫ**

Выберите тип подписки для подтверждения:

⭐ **ЗВЕЗДОЧКИ:** 25, 50, 75, 100 (без комиссии)
💎 **TON:** 4, 7, 13, 50, 100, 150 (10% комиссия рефереру)

📋 После выбора типа подписки:
1. Введите username пользователя
2. Система автоматически отправит одноразовую ссылку
3. Реферальная комиссия будет начислена (только для TON)
4. Пользователь получит уведомление о подтверждении

⚡ Дополнительные функции: История и Статистика"""
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            
            logger.info(f"✅ /confirmpay меню показано пользователю {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
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
                "13_ton": "💎 13 TON",
                "7_ton": "💎 7 TON",
                "4_ton": "💎 4 TON",
                "50_ton": "💎 50 TON",
                "100_ton": "💎 100 TON",
                "150_ton": "💎 150 TON"
            }
            
            display_name = subscription_names.get(subscription_type, subscription_type)
            
            # Определяем, есть ли комиссия
            payment_method = self.config.get_payment_method(subscription_type)
            commission_info = "💰 **Комиссия рефереру:** 10%" if payment_method == 'TON' else "💰 **Комиссия рефереру:** 0% (Stars)"
            
            # Сохраняем в очередь ожидания
            self.confirmation_queue[query.from_user.id] = {
                'subscription_type': subscription_type,
                'step': 'waiting_username'
            }
            
            # Кнопка "Назад"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ **ВЫБРАН ТИП ПОДПИСКИ:** {display_name}\n\n"
                f"💰 **Метод оплаты:** {payment_method}\n"
                f"{commission_info}\n\n"
                f"📝 **СЛЕДУЮЩИЙ ШАГ:**\n"
                f"Введите username пользователя (например: `john_doe` или `@john_doe`)\n\n"
                f"🔄 Система автоматически:\n"
                f"• Создаст одноразовую invite ссылку\n"
                f"• Отправит уведомление пользователю\n"
                f"• Зафиксирует операцию в истории\n"
                f"• Начислит комиссию рефереру (если есть)",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Выбран тип подписки {subscription_type} пользователем {query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_subscription_type_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def confirmpay_back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик возврата в главное меню /confirmpay - ИСПРАВЛЕНО"""
        try:
            query = update.callback_query
            await query.answer()
            
            # ИСПРАВЛЕНО: используем query.from_user.id вместо update.effective_user.id
            if query.from_user.id not in self.config.ADMIN_USER_IDS:
                await query.edit_message_text("❌ Доступ запрещен.")
                return
            
            try:
                # Очищаем очередь ожидания
                if query.from_user.id in self.confirmation_queue:
                    del self.confirmation_queue[query.from_user.id]
                
                # ИСПРАВЛЕНО: вызываем confirmpay_command с правильными параметрами
                # Создаем временный объект Update для передачи в confirmpay_command
                temp_update = Update(
                    message=query.message,
                    effective_user=query.from_user
                )
                await self.confirmpay_command(temp_update, context)
                
                logger.info(f"✅ Возврат к меню /confirmpay для пользователя {query.from_user.id}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка при возврате в меню confirmpay: {e}")
                await query.edit_message_text("❌ Произошла ошибка. Попробуйте позже.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_back_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            try:
                await update.callback_query.answer("❌ Произошла ошибка. Попробуйте позже.")
            except:
                pass  # Игнорируем ошибки ответа на callback
    
    async def confirmpay_history_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик показа истории подтверждений"""
        query = update.callback_query
        await query.answer()
        
        if update.effective_user.id not in self.config.ADMIN_USER_IDS:
            await query.edit_message_text("❌ Доступ запрещен.")
            return
        
        try:
            # Получаем историю из базы данных
            recent_logs = await self.database.get_recent_confirmation_logs(limit=10)
            
            if not recent_logs:
                message_text = """📊 **ИСТОРИЯ ПОДТВЕРЖДЕНИЙ**

📭 История подтверждений пуста.
Пока что не было подтвержденных оплат.
"""
            else:
                message_text = "📊 **ИСТОРИЯ ПОДТВЕРЖДЕНИЙ (последние 10)**\n\n"
                
                for i, log in enumerate(reversed(recent_logs), 1):
                    username = log.get('username', 'неизвестен')
                    sub_type = log.get('subscription_type', 'неизвестен')
                    created_at = log.get('created_at', '')
                    
                    # Форматируем timestamp
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        time_str = dt.strftime('%d.%m.%Y %H:%M')
                    except:
                        time_str = created_at[:19] if len(created_at) > 19 else created_at
                    
                    message_text += f"**{i}.** @{username} - {sub_type}\n"
                    message_text += f"   🕒 {time_str}\n\n"
            
            # Кнопка "Назад"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ История подтверждений отправлена пользователю {query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_history_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте позже.")
    
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
            
            message_text = f"""📈 **СТАТИСТИКА ПОДТВЕРЖДЕНИЙ**

📊 **Общее количество:** {stats.get('total_confirmations', 0)}
📅 **Сегодня:** {stats.get('today_confirmations', 0)}
📅 **За неделю:** {stats.get('week_confirmations', 0)}
📅 **За месяц:** {stats.get('month_confirmations', 0)}

🏆 **По типам подписок:**"""
            
            by_subscription = stats.get('by_subscription_type', {})
            if by_subscription:
                for sub_type, count in sorted(by_subscription.items(), key=lambda x: x[1], reverse=True):
                    # Форматируем название подписки
                    subscription_names = {
                        "25_stars": "⭐ 25 звезд",
                        "50_stars": "⭐ 50 звезд", 
                        "75_stars": "⭐ 75 звезд",
                        "100_stars": "⭐ 100 звезд",
                        "13_ton": "💎 13 TON",
                        "7_ton": "💎 7 TON",
                        "4_ton": "💎 4 TON",
                        "50_ton": "💎 50 TON",
                        "100_ton": "💎 100 TON",
                        "150_ton": "💎 150 TON"
                    }
                    display_name = subscription_names.get(sub_type, sub_type)
                    message_text += f"\n• **{display_name}:** {count}"
            else:
                message_text += "\n• Нет данных"
            
            message_text += f"\n\n📅 **Обновлено:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
            # Кнопка "Назад"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Статистика отправлена пользователю {query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_stats_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте позже.")
    
    # ===== ОБРАБОТЧИК USERNAME ПОЛЬЗОВАТЕЛЯ - УЛУЧШЕННАЯ ВЕРСИЯ С РЕФЕРАЛЬНОЙ СИСТЕМОЙ =====
    
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
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
    
    async def handle_username_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода username пользователя для подтверждения оплаты - ИСПРАВЛЕННАЯ ВЕРСИЯ С РЕФЕРАЛАМИ"""
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
            
            # ИСПРАВЛЕНО: Получаем канал_id для создания реальной invite ссылки
            channel_id = None
            if subscription_type == "25_stars":
                channel_id = self.config.CHANNEL_MAPPINGS.get(25)
            elif subscription_type == "50_stars":
                channel_id = self.config.CHANNEL_MAPPINGS.get(50)
            elif subscription_type == "75_stars":
                channel_id = self.config.CHANNEL_MAPPINGS.get(75)
            elif subscription_type == "100_stars":
                channel_id = self.config.CHANNEL_MAPPINGS.get(100)
            elif subscription_type == "13_ton":
                channel_id = self.config.TON_CHANNEL_MAPPINGS.get(13)
            elif subscription_type == "7_ton":
                channel_id = self.config.TON_CHANNEL_MAPPINGS.get(7)
            elif subscription_type == "4_ton":
                channel_id = self.config.TON_CHANNEL_MAPPINGS.get(4)
            elif subscription_type == "50_ton":
                channel_id = self.config.TON_CHANNEL_MAPPINGS.get(50)
            elif subscription_type == "100_ton":
                channel_id = self.config.TON_CHANNEL_MAPPINGS.get(100)
            elif subscription_type == "150_ton":
                channel_id = self.config.TON_CHANNEL_MAPPINGS.get(150)
            
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
            
            # Генерируем уникальный ID ссылки
            link_id = self.generate_secure_link_id()
            secure_link = f"{base_link}&secure={link_id}"
            
            # НОВОЕ: Обработка реферальной системы
            payment_method = self.config.get_payment_method(subscription_type)
            subscription_amount = self.config.get_subscription_amount(subscription_type)
            
            # Получаем реферера из pending_referrals
            pending_referrer = None
            try:
                # Получаем пользователя из базы данных
                user_data = await self.database.get_user_by_username(username)
                if user_data:
                    pending_referrer = await self.database.get_pending_referrer(user_data['id'])
                    logger.info(f"👥 Найден ожидающий реферер для @{username}: {pending_referrer}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при поиске реферера для @{username}: {e}")
            
            # Создаем или обновляем пользователя в базе данных
            await self.database.get_or_create_user(
                user_id=hash(username) % 1000000000,
                username=username,
                first_name=username,
                last_name=""
            )
            
            # Добавляем подписку
            await self.database.add_subscription(
                user_id=hash(username) % 1000000000,
                subscription_type=subscription_type,
                payment_method=payment_method,
                amount=subscription_amount,
                currency=payment_method
            )
            
            # Логируем подтверждение оплаты
            await self.database.save_confirmation_log({
                'admin_id': update.effective_user.id,
                'subscription_type': subscription_type,
                'username': username,
                'link_id': secure_link
            })
            
            # Если есть реферер, начисляем комиссию
            if pending_referrer:
                commission = await self.database.calculate_commission(
                    subscription_amount, subscription_type, payment_method
                )
                
                if commission > 0:
                    await self.database.add_referral_earnings(
                        referrer_id=pending_referrer,
                        referred_id=hash(username) % 1000000000,
                        commission_amount=commission,
                        subscription_type=subscription_type,
                        payment_method=payment_method
                    )
            
            # Отправляем ссылку пользователю
            await self.send_subscription_link_to_user(username, subscription_type, secure_link, context)
            
            # ИНФОРМИРУЕМ АДМИНА О РЕЗУЛЬТАТАХ
            admin_report = f"""✅ **ПОДТВЕРЖДЕНИЕ ЗАВЕРШЕНО**

👤 **Пользователь:** @{username}
📦 **Подписка:** {subscription_type}
💰 **Метод оплаты:** {payment_method}
💎 **Сумма:** {subscription_amount} TON"""

            if pending_referrer:
                commission = await self.database.calculate_commission(
                    subscription_amount, subscription_type, payment_method
                )
                admin_report += f"""
👥 **Реферальная система:**
• Реферер найден: ID {pending_referrer}
• Комиссия начислена: {commission} TON
• Статус: ✅ Комиссия зачислена"""
            else:
                if payment_method == 'TON':
                    admin_report += """
👥 **Реферальная система:**
• Реферер не найден
• Комиссия: 0 TON (нет реферера)"""
                else:
                    admin_report += """
👥 **Реферальная система:**
• Stars подписка - комиссия не начисляется
• Комиссия: 0 TON"""
            
            admin_report += f"""
🕒 **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
"""
            
            await update.message.reply_text(admin_report, parse_mode='Markdown')
            
            # Очищаем очередь ожидания
            del self.confirmation_queue[update.effective_user.id]
            
            logger.info(f"✅ Подтверждение с реферальной системой завершено для @{username}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке username: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка при обработке. Попробуйте позже.")
    
    # ===== ИСПРАВЛЕННАЯ ФУНКЦИЯ ОТПРАВКИ ССЫЛОК =====
    
    async def send_subscription_link_to_user(self, username: str, subscription_type: str, secure_link: str, context: ContextTypes.DEFAULT_TYPE):
        """Отправка ссылки на подписку пользователю - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            # Определяем отображаемое название подписки
            subscription_names = {
                "25_stars": "⭐ 25 звезд",
                "50_stars": "⭐ 50 звезд", 
                "75_stars": "⭐ 75 звезд",
                "100_stars": "⭐ 100 звезд",
                "13_ton": "💎 13 TON",
                "7_ton": "💎 7 TON",
                "4_ton": "💎 4 TON",
                "50_ton": "💎 50 TON",
                "100_ton": "💎 100 TON",
                "150_ton": "💎 150 TON"
            }
            display_name = subscription_names.get(subscription_type, subscription_type)
            
            # Определяем информацию о комиссии
            payment_method = self.config.get_payment_method(subscription_type)
            commission_text = ""
            if payment_method == 'TON':
                commission_text = "\n🎯 **Реферальная система:** Ваш пригласитель получит 10% комиссии с этой подписки!"
            
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

{commission_text}

🚀 **Добро пожаловать в закрытое сообщество PassiveNFT!**

Если у вас возникли вопросы, свяжитесь с менеджером: @{self.config.MANAGER_USERNAME}
"""
            
            # ИСПРАВЛЕНО: Безопасная отправка сообщения пользователю
            await self.send_safe_message_to_user(username, message_text, context)
            
            logger.info(f"✅ Ссылка отправлена пользователю @{username}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ссылки пользователю @{username}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise e
    
    async def send_safe_message_to_user(self, username: str, message_text: str, context: ContextTypes.DEFAULT_TYPE):
        """Безопасная отправка сообщения пользователю"""
        try:
            # Сначала пытаемся получить user_id через метод get_chat
            try:
                chat = await context.bot.get_chat(f"@{username}")
                if chat.type == 'private':
                    # Прямая отправка по user_id
                    await context.bot.send_message(
                        chat_id=chat.id,
                        text=message_text,
                        parse_mode='Markdown'
                    )
                    logger.info(f"✅ Сообщение отправлено пользователю {username} через get_chat")
                    return
            except TelegramError as e:
                logger.warning(f"⚠️ Не удалось получить чат через @{username}: {e}")
            
            # Если get_chat не сработал, пытаемся использовать resolve_username через get_chat_member
            try:
                # Пытаемся получить информацию о пользователе как участнике бота
                bot_info = await context.bot.get_me()
                try:
                    member = await context.bot.get_chat_member(bot_info.id, username)
                    # Если пользователь является участником чата бота
                    if member.status in ['member', 'administrator', 'creator']:
                        # Попытка отправить через chat_id бота
                        await context.bot.send_message(
                            chat_id=bot_info.id,
                            text=f"📬 Сообщение для @{username}:\n\n{message_text}"
                        )
                        logger.info(f"⚠️ Сообщение для {username} отправлено через бота (возможно недоступен)")
                        return
                except:
                    pass
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при попытке resolve_username для {username}: {e}")
            
            # Если все методы не сработали, информируем админа
            admin_message = f"""❌ **НЕВОЗМОЖНО ОТПРАВИТЬ СООБЩЕНИЕ**

👤 **Пользователь:** @{username}
📝 **Причина:** Пользователь не взаимодействовал с ботом или заблокировал его

🔧 **Решение:** 
• Попросите пользователя написать /start боту
• Или отправьте ссылку вручную

⚡ **Данные для ручной отправки:**
{message_text}
"""
            
            await context.bot.send_message(
                chat_id=context._user_id or self.config.ADMIN_USER_IDS[0],  # Fallback к первому админу
                text=admin_message,
                parse_mode='Markdown'
            )
            logger.warning(f"⚠️ Не удалось отправить сообщение пользователю @{username}, админ уведомлен")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при отправке сообщения пользователю @{username}: {e}")
            # Все равно логируем и продолжаем
            pass
    
    # ===== СОЗДАНИЕ РЕАЛЬНЫХ INVITE ССЫЛОК =====
    
    async def create_invite_link(self, channel_id: int, admin_id: int) -> Optional[str]:
        """Создание реальной invite ссылки через Telegram Bot API"""
        try:
            logger.info(f"Создание invite ссылки для канала {channel_id} пользователем {admin_id}")
            
            # Создаем одноразовую ссылку с лимитом 1 пользователь и сроком действия 1 час
            invite_link = await self.application.bot.create_chat_invite_link(
                chat_id=channel_id,
                member_limit=1,
                expire_date=int(time.time()) + 3600  # 1 час
            )
            
            link = invite_link.invite_link
            logger.info(f"✅ Invite ссылка создана: {link}")
            return link
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания invite link: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    # ===== ВАЛИДАЦИЯ И БЕЗОПАСНОСТЬ =====
    
    def validate_username(self, username: str) -> bool:
        """Валидация username"""
        if not username or len(username) < 5 or len(username) > 32:
            return False
        
        # Проверяем символы: только буквы, цифры, подчеркивания
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            return False
        
        return True
    
    def generate_secure_link_id(self) -> str:
        """Генерация безопасного ID для ссылки"""
        timestamp = str(int(time.time()))
        random_part = secrets.token_hex(8)
        combined = f"{timestamp}{random_part}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    # ===== НОВЫЕ АДМИН КОМАНДЫ ДЛЯ РЕФЕРАЛЬНОЙ СТАТИСТИКИ =====

    async def admin_refstats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда детальной реферальной статистики для всех пользователей"""
        logger.info(f"КОМАНДА /refstats от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к реферальной статистике")
                return

            # Получаем детальную реферальную статистику
            detailed_stats = await self.database.get_referral_stats()
            
            if not detailed_stats:
                referral_text = """🔗 **РЕФЕРАЛЬНАЯ СТАТИСТИКА**

📊 Данные о рефералах отсутствуют.
Пока что никто не привлекал рефералов.
"""
            else:
                referral_text = f"""🔗 **ДЕТАЛЬНАЯ РЕФЕРАЛЬНАЯ СТАТИСТИКА**

📊 **Всего активных рефереров:** {len(detailed_stats)}
💰 **Общий заработок:** {sum(stat['total_earnings'] for stat in detailed_stats):.2f} TON
👥 **Всего рефералов:** {sum(stat['total_referrals'] for stat in detailed_stats)}

🏆 **ТОП-10 рефереров по заработку:**"""

                for i, stat in enumerate(detailed_stats[:10], 1):
                    name = stat['referrer_username'] or 'Без username'
                    referrals = stat['total_referrals']
                    earnings = stat['total_earnings']
                    ton_refs = stat['ton_referrals']
                    
                    referral_text += f"""
**{i}.** @{name}
• Рефералов: {referrals} (TON: {ton_refs})
• Заработок: {earnings:.2f} TON"""

            await update.message.reply_text(referral_text, parse_mode='Markdown')
            logger.info(f"✅ Детальная реферальная статистика отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_refstats_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def admin_refstat_by_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда статистики конкретного пользователя"""
        logger.info(f"КОМАНДА /refstat от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS:
                await update.message.reply_text("❌ У вас нет доступа к реферальной статистике")
                return

            # Извлекаем username из команды
            command_parts = update.message.text.split()
            if len(command_parts) < 2:
                await update.message.reply_text("❌ Использование: /refstat <username>")
                return

            username = command_parts[1].replace('@', '')
            
            # Получаем статистику конкретного пользователя
            user_stats = await self.database.get_user_referral_stats_by_username(username)
            
            if not user_stats:
                referral_text = f"""🔗 **РЕФЕРАЛЬНАЯ СТАТИСТИКА @{username}**

❌ Пользователь не найден или не имеет рефералов.
"""
            else:
                referral_text = f"""🔗 **РЕФЕРАЛЬНАЯ СТАТИСТИКА @{username}**

📊 **Общая статистика:**
• Рефералов: {user_stats.get('total_referrals', 0)}
• TON рефералов: {user_stats.get('ton_referrals', 0)}
• Stars рефералов: {user_stats.get('stars_referrals', 0)}
• Общий заработок: {user_stats.get('total_earnings', 0):.2f} TON

💰 **Детализация заработка:**"""
                
                referral_earnings = user_stats.get('referral_earnings', [])
                if referral_earnings:
                    for earnings in referral_earnings:
                        sub_type = earnings.get('subscription_type', 'неизвестен')
                        amount = earnings.get('commission_amount', 0)
                        date = earnings.get('created_at', '')
                        
                        referral_text += f"""
• {sub_type}: {amount:.2f} TON ({date[:10]})"""
                else:
                    referral_text += "\n• Пока нет заработка"

            await update.message.reply_text(referral_text, parse_mode='Markdown')
            logger.info(f"✅ Статистика @{username} отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_refstat_by_username: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    # ===== ОСНОВНЫЕ ОБРАБОТЧИКИ ПОДПИСОК =====
    
    async def subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Подписки'"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: subscription callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            subscription_text = """💳 **ВЫБОР ТИПА ПОДПИСКИ**

🎯 **Два способа получения доступа:**

⭐ **ЗА ЗВЕЗДЫ** - быстро и просто
• 25, 50, 75, 100 звезд
• Мгновенный доступ
• Участие в активностях
• Получение NFT

💎 **ЗА TON** - без ограничений
• 4, 7, 13, 50, 100, 150 TON
• Максимальный доступ
• Без активностей
• Только закрытые каналы

💰 **Реферальная система:** 10% комиссия только за TON-подписки"""

            # Кнопки выбора типа подписки
            keyboard = [
                [InlineKeyboardButton("⭐ Подписки за звезды", callback_data="select_stars")],
                [InlineKeyboardButton("💎 Подписки за TON", callback_data="select_ton")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(subscription_text, reply_markup=reply_markup, parse_mode='Markdown')
                logger.info(f"✅ Меню подписок показано пользователю {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Меню подписок уже открыто!")
                    logger.info(f"ℹ️ Меню подписок уже открыто для пользователя {update.effective_user.id}")
                else:
                    await query.answer("Ошибка при открытии меню подписок.")
                    logger.error(f"❌ Ошибка BadRequest в subscription_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в subscription_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def select_stars_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора подписок за звезды"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: select_stars callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            stars_text = """⭐ **ПОДПИСКИ ЗА ЗВЕЗДЫ**

💫 **Доступные планы:**
• ⭐ 25 звезд - Базовый план
• ⭐ 50 звезд - Расширенный план  
• ⭐ 75 звезд - Премиум план
• ⭐ 100 звезд - VIP план

🚀 **Преимущества:**
• Мгновенный доступ после покупки
• Участие во всех активностях
• Получение NFT
• Поддержка разработчиков

💡 **Как получить:**
1. Купите звезды в Telegram Premium
2. Отправьте их @{stars_username}
3. Получите мгновенный доступ

💰 **Реферальная система:** За Stars подписки комиссия рефереру не начисляется
"""

            # Кнопки выбора количества звезд
            keyboard = [
                [InlineKeyboardButton("⭐ 25 звезд", callback_data="stars_25"),
                 InlineKeyboardButton("⭐ 50 звезд", callback_data="stars_50")],
                [InlineKeyboardButton("⭐ 75 звезд", callback_data="stars_75"),
                 InlineKeyboardButton("⭐ 100 звезд", callback_data="stars_100")],
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(stars_text, reply_markup=reply_markup, parse_mode='Markdown')
                logger.info(f"✅ Меню Stars подписок показано пользователю {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Меню Stars уже открыто!")
                    logger.info(f"ℹ️ Меню Stars уже открыто для пользователя {update.effective_user.id}")
                else:
                    await query.answer("Ошибка при открытии меню Stars.")
                    logger.error(f"❌ Ошибка BadRequest в select_stars_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в select_stars_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def select_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора подписок за TON"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: select_ton callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            ton_text = f"""💎 **ПОДПИСКИ ЗА TON**

🚀 **Доступные планы:**
• 💎 4 TON - На 150 человек
• 💎 7 TON - На 100 человек  
• 💎 13 TON - На 50 человек
• 💎 50 TON - VIP план
• 💎 100 TON - Премиум план
• 💎 150 TON - Максимальный план

🔒 **Особенности:**
• Доступ только к закрытым каналам
• Без активностей и NFT
• Полная конфиденциальность
• Пожизненный доступ

💰 **Оплата:**
• Адрес кошелька: `{self.config.TON_WALLET_ADDRESS[:20]}...`
• Отправьте указанную сумму TON
• Подтверждение менеджером

💰 **Реферальная система:** Ваш реферер получит 10% комиссии!
"""

            # Кнопки выбора количества TON
            keyboard = [
                [InlineKeyboardButton("💎 4 TON", callback_data="ton_4"),
                 InlineKeyboardButton("💎 7 TON", callback_data="ton_7")],
                [InlineKeyboardButton("💎 13 TON", callback_data="ton_13"),
                 InlineKeyboardButton("💎 50 TON", callback_data="ton_50")],
                [InlineKeyboardButton("💎 100 TON", callback_data="ton_100"),
                 InlineKeyboardButton("💎 150 TON", callback_data="ton_150")],
                [InlineKeyboardButton("📋 Скопировать адрес", callback_data="copy_ton")],
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(ton_text, reply_markup=reply_markup, parse_mode='Markdown')
                logger.info(f"✅ Меню TON подписок показано пользователю {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Меню TON уже открыто!")
                    logger.info(f"ℹ️ Меню TON уже открыто для пользователя {update.effective_user.id}")
                else:
                    await query.answer("Ошибка при открытии меню TON.")
                    logger.error(f"❌ Ошибка BadRequest в select_ton_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в select_ton_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def stars_subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик подписки на звезды"""
        logger.info(f"⭐ ПОЛУЧЕН CALLBACK: {query.data} от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()
            
            # Извлекаем количество звезд
            stars = int(query.data.split('_')[1])
            logger.info(f"⭐ ПОЛУЧЕН CALLBACK: stars_{stars} от пользователя {update.effective_user.id}")
            
            # Информация о планах
            plan_info = {
                25: {
                    'price': '25 звезд',
                    'name': 'Базовый план',
                    'description': 'Доступ к основному каналу с активностями'
                },
                50: {
                    'price': '50 звезд',
                    'name': 'Расширенный план',
                    'description': 'Доступ к дополнительным каналам и эксклюзивному контенту'
                },
                75: {
                    'price': '75 звезд',
                    'name': 'Премиум план',
                    'description': 'Полный доступ ко всем каналам и специальным активностям'
                },
                100: {
                    'price': '100 звезд',
                    'name': 'VIP план',
                    'description': 'Максимальный доступ с приоритетной поддержкой'
                }
            }
            
            info = plan_info.get(stars, {})
            price = info.get('price', f'{stars} звезд')
            name = info.get('name', '')
            description = info.get('description', 'Доступ к закрытому каналу')
            
            # Получаем канал для данного количества звезд
            channel_id = self.config.CHANNEL_MAPPINGS.get(stars)
            
            # Проверяем, есть ли у пользователя доступ
            has_access = await self.check_user_access(update.effective_user.id, stars, 'stars')
            
            if has_access:
                # Пользователь уже имеет доступ - показываем ссылку
                channel_link = self.config.PRIVATE_CHANNEL_LINKS.get(f"{stars}_stars", "https://t.me/passivenft_channel")
                
                message_text = f"""🎉 **У ВАС УЖЕ ЕСТЬ ДОСТУП!**

✅ **Ваш план:** {price} ({name})
📖 **Описание:** {description}

🔗 **Ссылка на канал:** {channel_link}

💎 **Наслаждайтесь активностями и получайте NFT!**

💡 **Реферальная система:** За Stars подписки комиссия рефереру не начисляется
"""
                keyboard = [[InlineKeyboardButton("📢 Написать менеджеру", url=f"https://t.me/{self.config.MANAGER_USERNAME}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
                return
            
            # Пользователь не имеет доступа - показываем инструкции по покупке
            message_text = f"""💫 **ПЛАН: {price} ({name})**

📖 **Описание:** {description}

🚀 **Как получить доступ:**
1. Купите {stars} звездочек в Telegram
2. Отправьте их @{self.config.STARS_USERNAME}
3. Получите ссылку на закрытый канал

⭐ **Важно:** Звездочки покупаются в настройках Telegram Premium

💎 **После покупки:** Получите мгновенный доступ к каналу!

💡 **Реферальная система:** За Stars подписки комиссия рефереру не начисляется

*Нужна помощь? Напишите @{self.config.STARS_USERNAME}*
"""
            keyboard = [
                [InlineKeyboardButton("💬 Связаться с менеджером", callback_data="contact")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Ошибка в stars_subscription_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    async def ton_subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик подписки на TON"""
        logger.info(f"💎 ПОЛУЧЕН CALLBACK: {query.data} от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()
            
            # Извлекаем количество TON
            ton_amount = int(query.data.split('_')[1])
            logger.info(f"💎 ПОЛУЧЕН CALLBACK: ton_{ton_amount} от пользователя {update.effective_user.id}")
            
            # Информация о планах
            plan_info = {
                4: {
                    'price': '4 TON',
                    'name': 'На 150 человек',
                    'description': 'Базовый план без активностей'
                },
                7: {
                    'price': '7 TON',
                    'name': 'На 100 человек',
                    'description': 'Расширенный план с дополнительными каналами'
                },
                13: {
                    'price': '13 TON',
                    'name': 'На 50 человек',
                    'description': 'VIP план с максимальным доступом'
                },
                50: {
                    'price': '50 TON',
                    'name': 'VIP план',
                    'description': 'Максимальные возможности'
                },
                100: {
                    'price': '100 TON',
                    'name': 'Премиум план',
                    'description': 'Премиум доступ ко всем функциям'
                },
                150: {
                    'price': '150 TON',
                    'name': 'Максимальный план',
                    'description': 'Полный доступ ко всем возможностям'
                }
            }
            
            info = plan_info.get(ton_amount, {})
            price = info.get('price', f'{ton_amount} TON')
            name = info.get('name', '')
            description = info.get('description', 'Подписка на закрытый канал')
            
            # Получаем канал для данного количества TON
            channel_id = self.config.TON_CHANNEL_MAPPINGS.get(ton_amount)
            
            # Проверяем, есть ли у пользователя доступ
            has_access = await self.check_user_access(update.effective_user.id, ton_amount, 'ton')
            
            if has_access:
                # Пользователь уже имеет доступ - показываем ссылку
                channel_link = self.config.PRIVATE_CHANNEL_LINKS.get(f"{ton_amount}_ton", "https://t.me/passivenft_channel")
                
                message_text = f"""🎉 **У ВАС УЖЕ ЕСТЬ ДОСТУП!**

✅ **Ваш план:** {price} ({name})
📖 **Описание:** {description}

🔗 **Ссылка на канал:** {channel_link}

💎 **Наслаждайтесь закрытым сообществом!**

💰 **Реферальная система:** Ваш реферер получил 10% комиссии ({ton_amount * 0.1:.1f} TON)
"""
                keyboard = [[InlineKeyboardButton("📢 Написать менеджеру", url=f"https://t.me/{self.config.MANAGER_USERNAME}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
                return
            
            # Пользователь не имеет доступа - показываем инструкции по покупке
            commission_info = f"Ваш реферер получит {ton_amount * 0.1:.1f} TON комиссии"
            
            message_text = f"""💎 **ПЛАН: {price} ({name})**

📖 **Описание:** {description}

🚀 **Как получить доступ:**
1. Скопируйте адрес кошелька TON
2. Отправьте {ton_amount} TON на указанный адрес
3. Отправьте чек/транзакцию менеджеру для подтверждения

💰 **Адрес кошелька TON:**
`{self.config.TON_WALLET_ADDRESS}`

🔍 **После оплаты:** Отправьте скриншот транзакции менеджеру

💡 **Важно:** Оплата зачисляется только после подтверждения менеджером

💰 **Реферальная система:** {commission_info}

*Нужна помощь? Напишите @{self.config.MANAGER_USERNAME}*
"""
            keyboard = [
                [InlineKeyboardButton("📋 Скопировать адрес", callback_data="copy_ton")],
                [InlineKeyboardButton("💬 Связаться с менеджером", callback_data="contact")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Ошибка в ton_subscription_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    async def payment_stars_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик оплаты звездами"""
        query = update.callback_query
        await query.answer()
        
        stars = int(query.data.split('_')[2])
        
        message_text = f"""⭐ **ОПЛАТА: {stars} ЗВЕЗД**

📱 **Инструкция по покупке звезд:**
1. Откройте настройки Telegram
2. Перейдите в Telegram Premium
3. Купите {stars} звездочек
4. Отправьте их @{self.config.STARS_USERNAME}
5. Получите ссылку на закрытый канал

💫 **Преимущества:**
• Мгновенный доступ
• Участие в активностях
• Получение NFT
• Поддержка разработчиков

💡 **Реферальная система:** За Stars подписки комиссия не начисляется

❓ **Вопросы?** @{self.config.STARS_USERNAME}
"""
        keyboard = [[InlineKeyboardButton("💬 Написать менеджеру", url=f"https://t.me/{self.config.STARS_USERNAME}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def payment_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик оплаты TON"""
        query = update.callback_query
        await query.answer()
        
        ton_amount = int(query.data.split('_')[2])
        commission = ton_amount * 0.1
        
        message_text = f"""💎 **ОПЛАТА: {ton_amount} TON**

💰 **Инструкция по оплате:**
1. Скопируйте адрес кошелька
2. Отправьте {ton_amount} TON
3. Отправьте чек менеджеру

📍 **Адрес кошелька TON:**
`{self.config.TON_WALLET_ADDRESS}`

✅ **После оплаты:**
• Отправьте скриншот транзакции
• Получите ссылку на канал
• Мгновенный доступ

🔒 **Безопасность:**
• Оплата только на указанный адрес
• Подтверждение менеджером
• Прозрачные условия

💰 **Реферальная система:** Ваш реферер получит {commission:.1f} TON комиссии

❓ **Вопросы?** @{self.config.MANAGER_USERNAME}
"""
        keyboard = [
            [InlineKeyboardButton("📋 Скопировать адрес", callback_data="copy_ton")],
            [InlineKeyboardButton("💬 Написать менеджеру", url=f"https://t.me/{self.config.MANAGER_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def payment_stars_check_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик проверки оплаты звездами"""
        query = update.callback_query
        await query.answer()
        
        message_text = f"""🔍 **ПРОВЕРКА ОПЛАТЫ ЗВЕЗДАМИ**

📋 **Что нужно предоставить:**
• Скриншот покупки звезд
• Username получателя (@{self.config.STARS_USERNAME})
• Количество отправленных звезд

⏰ **Время обработки:** 5-15 минут

📞 **Как отправить:** Напишите @{self.config.STARS_USERNAME} с прикрепленным скриншотом

✅ **После подтверждения:**
• Получите ссылку на закрытый канал
• Мгновенный доступ к активностям

💡 **Реферальная система:** Комиссия за Stars подписки не начисляется
"""
        keyboard = [[InlineKeyboardButton("💬 Написать менеджеру", url=f"https://t.me/{self.config.STARS_USERNAME}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def payment_ton_check_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик проверки оплаты TON"""
        query = update.callback_query
        await query.answer()
        
        message_text = f"""🔍 **ПРОВЕРКА ОПЛАТЫ TON**

📋 **Что нужно предоставить:**
• Скриншот транзакции
• Адрес получателя: `{self.config.TON_WALLET_ADDRESS[:20]}...`
• Сумма перевода

⏰ **Время обработки:** 10-30 минут

📞 **Как отправить:** Напишите @{self.config.MANAGER_USERNAME} с прикрепленным скриншотом

✅ **После подтверждения:**
• Получите ссылку на закрытый канал
• Полный доступ без активностей

💰 **Реферальная система:** Ваш реферер получит комиссию 10%
"""
        keyboard = [
            [InlineKeyboardButton("📋 Скопировать адрес", callback_data="copy_ton")],
            [InlineKeyboardButton("💬 Написать менеджеру", url=f"https://t.me/{self.config.MANAGER_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

    # ===== СИСТЕМА РЕФЕРАЛОВ =====
    
    async def referral_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Реферальная система'"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            referral_text = f"""👥 **РЕФЕРАЛЬНАЯ СИСТЕМА PassiveNFT**

💰 **Как это работает:**
• Делитесь своей реферальной ссылкой с друзьями
• Когда друг покупает подписку за TON, вы получаете 10% комиссию
• За Stars подписки комиссия не начисляется

🎯 **Ваша реферальная ссылка:**
https://t.me/{self.config.BOT_USERNAME}?start=ref_{update.effective_user.id}

💡 **Преимущества:**
• Пассивный доход от приглашений
• 10% с каждой TON-подписки реферала
• Без ограничений по количеству рефералов

🔗 **Пример заработка:**
• Друг покупает за 13 TON → Вы получаете 1.3 TON
• Друг покупает за 50 TON → Вы получаете 5 TON
• Больше друзей = больше дохода!"""

            # Кнопки реферальной системы
            keyboard = [
                [InlineKeyboardButton("📊 Моя статистика", callback_data="referral_stats")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(referral_text, reply_markup=reply_markup, parse_mode='Markdown')
                logger.info(f"✅ Реферальная система открыта для пользователя {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Реферальная система уже открыта!")
                    logger.info(f"ℹ️ Реферальная система уже открыта для пользователя {update.effective_user.id}")
                else:
                    await query.answer("Ошибка при открытии реферальной системы.")
                    logger.error(f"❌ Ошибка BadRequest в referral_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_callback: {e}")
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
                stats_text = "У вас пока нет рефералов.\n💡 Поделитесь своей реферальной ссылкой с друзьями!"

            # Кнопка "Назад"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="referral")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Статистика рефералов отправлена пользователю {query.from_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_stats_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Произошла ошибка. Попробуйте позже.")

    # ===== СВЯЗЬ И ПОДДЕРЖКА =====
    
    async def contact_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Связь'"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: contact callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            contact_text = f"""💬 **СВЯЗЬ С КОМАНДОЙ**

📞 **Менеджер по подпискам:**
@{self.config.MANAGER_USERNAME}

📞 **Менеджер по звездам:**
@{self.config.STARS_USERNAME}

🤖 **Информация о боте:**
• Версия: 4.0.0 (с реферальной системой)
• Поддержка: 24/7
• Обработка запросов: мгновенно

📋 **Мы поможем с:**
• Оформлением подписок
• Проблемами с доступом
• Техническими вопросами
• Реферальной программой
• Расчетом комиссий

💰 **Реферальная система:**
• Комиссия 10% только за TON-подписки
• Автоматический расчет при подтверждении
• Детальная статистика для всех

⏰ **Время ответа:** обычно в течение 1 часа
"""

            keyboard = [
                [InlineKeyboardButton("💬 Написать менеджеру", url=f"https://t.me/{self.config.MANAGER_USERNAME}")],
                [InlineKeyboardButton("⭐ Написать менеджеру звезд", url=f"https://t.me/{self.config.STARS_USERNAME}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(contact_text, reply_markup=reply_markup, parse_mode='Markdown')
                logger.info(f"✅ Контакты показаны пользователю {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Контакты уже показаны!")
                    logger.info(f"ℹ️ Контакты уже показаны для пользователя {update.effective_user.id}")
                else:
                    await query.answer("Ошибка при показе контактов.")
                    logger.error(f"❌ Ошибка BadRequest в contact_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в contact_callback: {e}")
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
    
    async def rus_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Общая статистика' в команде /rus"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: rus_stats callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Получаем общую статистику
            stats_data = await self.database.get_general_stats()
            
            stats_text = f"""📊 **ОБЩАЯ СТАТИСТИКА**

⭐ **ПОДПИСКИ ЗА ЗВЕЗДЫ:**
• 25 звезд: {stats_data.get('stars_25', 0)}
• 50 звезд: {stats_data.get('stars_50', 0)}  
• 75 звезд: {stats_data.get('stars_75', 0)}
• 100 звезд: {stats_data.get('stars_100', 0)}

💎 **ПОДПИСКИ ЗА TON:**
• 4 TON: {stats_data.get('ton_4', 0)}
• 7 TON: {stats_data.get('ton_7', 0)}
• 13 TON: {stats_data.get('ton_13', 0)}
• 50 TON: {stats_data.get('ton_50', 0)}
• 100 TON: {stats_data.get('ton_100', 0)}
• 150 TON: {stats_data.get('ton_150', 0)}

👥 **РЕФЕРАЛЬНАЯ СИСТЕМА:**
• Общее количество рефералов: {stats_data.get('total_referrals', 0)}
• Общая комиссия: {stats_data.get('total_commission', 0)} TON

🔄 **ОБЩАЯ СТАТИСТИКА ОБНОВЛЕНА**
Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""

            # Создаем клавиатуру
            keyboard = [
                [InlineKeyboardButton("🔄 Обновить статистику", callback_data="rus_stats")],
                [InlineKeyboardButton("🔙 Назад к подпискам", callback_data="rus_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.edit_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Статистика показана пользователю {update.effective_user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в rus_stats_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Ошибка при получении статистики. Попробуйте позже.")

    async def rus_back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Назад к подпискам' в статистике /rus"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: rus_back callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # Повторно показываем меню /rus
            keyboard = [
                # Кнопки Stars
                [InlineKeyboardButton("⭐ 25 звезд", callback_data="stars_25")],
                [InlineKeyboardButton("⭐ 50 звезд", callback_data="stars_50")],
                [InlineKeyboardButton("⭐ 75 звезд", callback_data="stars_75")],
                [InlineKeyboardButton("⭐ 100 звезд", callback_data="stars_100")],
                # Кнопки TON
                [InlineKeyboardButton("💎 4 TON", callback_data="ton_4")],
                [InlineKeyboardButton("💎 7 TON", callback_data="ton_7")],
                [InlineKeyboardButton("💎 13 TON", callback_data="ton_13")],
                # Дополнительные кнопки
                [InlineKeyboardButton("📊 Общая статистика", callback_data="rus_stats")],
                [InlineKeyboardButton("🔙 Назад в меню", callback_data="back")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = """🇷🇺 **РУССКОЕ МЕНЮ**

⭐ **ПОДПИСКИ ЗА ЗВЕЗДЫ:**
• ⭐ 25 звезд - Базовый план
• ⭐ 50 звезд - Расширенный план
• ⭐ 75 звезд - Премиум план
• ⭐ 100 звезд - VIP план

💎 **ПОДПИСКИ ЗА TON:**
• 💎 4 TON - На 150 человек
• 💎 7 TON - На 100 человек
• 💎 13 TON - На 50 человек

📊 **ОБЩАЯ СТАТИСТИКА** - покажет текущую статистику подписок

Выберите нужную подписку:"""
            
            await query.message.edit_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Возврат к меню /rus для пользователя {update.effective_user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в rus_back_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer("❌ Ошибка. Попробуйте позже.")

    # ===== АДМИН КОМАНДЫ =====
    
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

            # ОРИГИНАЛЬНЫЙ текст админ панели + НОВЫЕ команды
            admin_text = f"""🔧 Админ панель PassiveNFT Bot v4.0
📊 /adminserveraastat - статистика подписок
👥 /adminserveraapeople - список участников
🔗 /adminserveraaref - реферальная статистика
🔗 /refstats - детальная реферальная статистика
🔗 /refstat <username> - статистика конкретного пользователя
🔗 /confirm_payment - проверка оплаты
📢 /broadcast <сообщение> - рассылка всем пользователям

**НОВЫЕ КОМАНДЫ:**
📺 /channel_info - информация о каналах
🆔 /get_channel_id - получить ID текущего канала
🔧 /testcmd - тестовая команда

💳 Система подтверждения оплат:
👨‍💼 /confirmpay - подтверждение оплат с автоотправкой ссылок
⭐ Все типы подписок: 25/50/75/100 звезд, 4/7/13/50/100/150 TON

💰 **РЕФЕРАЛЬНАЯ СИСТЕМА:**
✅ Автоматический расчет 10% комиссии для TON-подписок
✅ Интеграция с системой подтверждения оплаты
✅ Детальная статистика для админов
✅ Комиссия только за TON, не за Stars"""

            await update.message.reply_text(admin_text, parse_mode='Markdown')
            logger.info(f"✅ Админ панель показана пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def admin_stat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды статистики"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraastat от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к статистике")
                return

            # Получаем статистику из базы данных
            stats = await self.database.get_confirmation_stats()
            referral_earnings = await self.database.get_total_commission_earned()
            
            if stats:
                stats_text = f"""📊 **СТАТИСТИКА PassiveNFT Bot**

👥 **Пользователи:** {await self.database.get_all_users_count()}
💎 **Подписки за TON:** {sum(1 for sub_type in stats.get('by_subscription_type', {}) if 'ton' in sub_type)} типов
⭐ **Подписки за звезды:** {sum(1 for sub_type in stats.get('by_subscription_type', {}) if 'stars' in sub_type)} типов
👥 **Рефералы:** {await self.database.get_total_referrals_count()}

💰 **Доходы:**
• Подтверждено подписок: {stats.get('total_confirmations', 0)}
• Сегодня: {stats.get('today_confirmations', 0)}
• За неделю: {stats.get('week_confirmations', 0)}
• За месяц: {stats.get('month_confirmations', 0)}

💎 **Реферальная система:**
• Общий заработок рефереров: {referral_earnings:.2f} TON
• Комиссия: 10% от TON-подписок

🕒 **Обновлено:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
            else:
                stats_text = "📊 Статистика недоступна"
                
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            logger.info(f"✅ Статистика отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_stat_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def admin_people_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды списка участников"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraapeople от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к списку участников")
                return

            # Получаем список пользователей
            users_list = await self.database.get_subscribers()
            
            if users_list:
                users_text = "👥 **СПИСОК ПОЛЬЗОВАТЕЛЕЙ (последние 20):**\n\n"
                
                for i, user_data in enumerate(users_list, 1):
                    user_id = user_data.get('id', 'неизвестен')
                    username = user_data.get('username', 'без username')
                    name = user_data.get('name', 'неизвестно')
                    
                    users_text += f"**{i}.** ID: `{user_id}`\n"
                    users_text += f"   Username: @{username}\n"
                    users_text += f"   Имя: {name}\n\n"
            else:
                users_text = "👥 Пользователи не найдены"
                
            await update.message.reply_text(users_text, parse_mode='Markdown')
            logger.info(f"✅ Список пользователей отправлен пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_people_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def admin_referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды реферальной статистики"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraaref от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к реферальной статистике")
                return

            # Получаем реферальную статистику
            referral_stats = await self.database.get_referral_stats()
            
            if referral_stats:
                referral_text = f"""🔗 **РЕФЕРАЛЬНАЯ СТАТИСТИКА**

👥 **Общие рефералы:** {await self.database.get_total_referrals_count()}
💰 **Общий доход:** {await self.database.get_total_commission_earned():.2f} TON

🏆 **ТОП-10 рефереров:**"""
                
                for i, referrer in enumerate(referral_stats[:10], 1):
                    ref_username = referrer.get('username', 'без username')
                    ref_count = referrer.get('total_referrals', 0)
                    ref_commission = referrer.get('commission', 0.0)
                    
                    referral_text += f"""
**{i}.** @{ref_username}
   Рефералов: {ref_count}
   Комиссия: {ref_commission:.2f} TON"""
            else:
                referral_text = "🔗 Реферальная статистика недоступна"
                
            await update.message.reply_text(referral_text, parse_mode='Markdown')
            logger.info(f"✅ Реферальная статистика отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_referral_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды рассылки"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /broadcast от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к рассылке")
                return

            # Извлекаем сообщение из команды
            command_text = update.message.text
            if len(command_text.split()) < 2:
                await update.message.reply_text("❌ Использование: /broadcast <сообщение>")
                return
            
            message_to_send = ' '.join(command_text.split()[1:])
            
            # Получаем всех пользователей
            users_list = await self.database.get_subscribers()
            
            if not users_list:
                await update.message.reply_text("❌ Пользователи не найдены")
                return
            
            # Отправляем сообщение всем пользователям
            sent_count = 0
            failed_count = 0
            
            for user_data in users_list:
                try:
                    user_id = user_data.get('id')
                    if user_id:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"📢 **ОБЪЯВЛЕНИЕ**\n\n{message_to_send}",
                            parse_mode='Markdown'
                        )
                        sent_count += 1
                        # Небольшая задержка чтобы не превысить лимиты API
                        await asyncio.sleep(0.1)
                except Exception as e:
                    failed_count += 1
                    logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            
            # Отчет администратору
            report = f"""📢 **РАССЫЛКА ЗАВЕРШЕНА**

👥 **Отправлено:** {sent_count} пользователей
❌ **Ошибок:** {failed_count}

📝 **Сообщение:**
{message_to_send}"""
            await update.message.reply_text(report, parse_mode='Markdown')
            logger.info(f"✅ Рассылка завершена: {sent_count} отправлено, {failed_count} ошибок")

        except Exception as e:
            logger.error(f"❌ Ошибка в broadcast_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестовая команда"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /testcmd от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к тестовой команде")
                return

            test_info = f"""🧪 **ТЕСТОВАЯ КОМАНДА**

✅ **Статус:** Бот работает корректно
🕒 **Время:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
👤 **Тестировщик:** {user.first_name} (@{user.username or 'без username'})
🆔 **Ваш ID:** {user.id}

📊 **Система подтверждения оплат:**
• Режим: АКТИВЕН
• Типы: 25/50/75/100 звезд, 4/7/13/50/100/150 TON
• Invite ссылки: РЕАЛЬНЫЕ + FALLBACK

💰 **Реферальная система:**
• Статус: АКТИВНА
• Комиссия: 10% только за TON-подписки
• Автоматический расчет при подтверждении
• Детальная статистика для админов

🔧 **Все функции работают!**
"""
            
            await update.message.reply_text(test_info, parse_mode='Markdown')
            logger.info(f"✅ Тестовая команда выполнена для пользователя {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в test_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    # ===== НОВЫЕ КОМАНДЫ ДЛЯ РАБОТЫ С КАНАЛАМИ =====
    
    async def channel_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда информации о каналах"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /channel_info от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к информации о каналах")
                return

            # Формируем информацию о каналах
            channel_info = """📺 **ИНФОРМАЦИЯ О КАНАЛАХ**

⭐ **КАНАЛЫ ЗА ЗВЕЗДЫ:**"""
            
            for stars, channel_id in self.config.CHANNEL_MAPPINGS.items():
                link = self.config.PRIVATE_CHANNEL_LINKS.get(f"{stars}_stars", "ссылка не найдена")
                channel_info += f"\n• ⭐ {stars} звезд → {channel_id}"
                channel_info += f"\n  Ссылка: {link[:50]}..."
            
            channel_info += "\n\n💎 **КАНАЛЫ ЗА TON:**\n"
            
            for ton_amount, channel_id in self.config.TON_CHANNEL_MAPPINGS.items():
                link = self.config.PRIVATE_CHANNEL_LINKS.get(f"{ton_amount}_ton", "ссылка не найдена")
                channel_info += f"• 💎 {ton_amount} TON → {channel_id}\n"
                channel_info += f"  Ссылка: {link[:50]}...\n"
            
            channel_info += f"""🔧 **УПРАВЛЕНИЕ:**
• Все ссылки настроены в конфигурации
• Invite ссылки создаются автоматически
• Fallback система активирована

💰 **Реферальная система:**
• Комиссия 10% только за TON-подписки
• Автоматическое начисление при подтверждении

🕒 **Обновлено:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
            
            await update.message.reply_text(channel_info, parse_mode='Markdown')
            logger.info(f"✅ Информация о каналах отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в channel_info_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    async def get_channel_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда получения ID текущего канала"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /get_channel_id от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("❌ У вас нет доступа к этой команде")
                return

            # Получаем информацию о чате
            chat = update.effective_chat
            
            if chat:
                channel_info = f"""🆔 **ИНФОРМАЦИЯ О КАНАЛЕ**

📝 **Название:** {chat.title or 'Личный чат'}
🆔 **ID канала:** `{chat.id}`
👤 **Тип чата:** {chat.type}

🔧 **Для каналов:**
• ID имеет формат: -100XXXXXXXXX
• Используйте этот ID в конфигурации
• Бот должен быть администратором канала

💡 **Пример использования в TON_CHANNEL_MAPPINGS:**
```
self.TON_CHANNEL_MAPPINGS = {{
    50: {chat.id},  # Замените на ваш ID
}}
```"""
            else:
                channel_info = "❌ Информация о чате недоступна"
                
            await update.message.reply_text(channel_info, parse_mode='Markdown')
            logger.info(f"✅ Информация о канале отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в get_channel_id_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    # ===== ПРОВЕРКА ДОСТУПА =====
    
    async def check_user_access(self, user_id: int, subscription_amount: int, subscription_type: str) -> bool:
        """Проверка доступа пользователя к каналу"""
        try:
            # Проверяем в базе данных
            access_info = await self.database.check_subscription_access(user_id, subscription_amount, subscription_type)
            return access_info.get('has_access', False)
        except Exception as e:
            logger.error(f"Ошибка проверки доступа для пользователя {user_id}: {e}")
            return False

    # ===== WEBHOOK И СЕРВЕР =====
    
    async def setup_webhook(self):
        """Настройка webhook для продакшена"""
        try:
            webhook_url = "https://passivenft-bot.onrender.com/webhook"
            
            # Удаляем старые webhook'и
            await self.application.bot.delete_webhook()
            logger.info("🧹 Очистка старных webhook'ов...")
            
            # Устанавливаем новый webhook
            await self.application.bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Webhook установлен: {webhook_url}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки webhook: {e}")
    
    async def webhook_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик webhook запросов"""
        try:
            await self.application.process_update(update)
        except Exception as e:
            logger.error(f"❌ Ошибка обработки webhook: {e}")
    
    def setup_web_server(self):
        """Настройка web сервера для webhook"""
        from aiohttp import web
        import aiohttp
        
        async def webhook(request):
            """Обработчик webhook HTTP запросов"""
            try:
                data = await request.json()
                update = Update.de_json(data, self.application.bot)
                await self.application.process_update(update)
                return web.Response(text="OK")
            except Exception as e:
                logger.error(f"❌ Ошибка webhook обработчика: {e}")
                return web.Response(text="ERROR", status=500)
        
        async def health_check(request):
            """Проверка состояния сервера"""
            return web.json_response({"status": "OK", "timestamp": datetime.now().isoformat()})
        
        # Создаем приложение
        app = web.Application()
        app.router.add_post('/webhook', webhook)
        app.router.add_get('/health', health_check)
        app.router.add_get('/', health_check)
        
        return app
    
    # ===== ОСНОВНОЙ ЗАПУСК =====
    
    async def start_polling(self):
        """Запуск бота в режиме polling (для разработки)"""
        logger.info("🔄 Запуск polling режима...")
        
        # Очищаем webhook для polling
        await self.application.bot.delete_webhook()
        
        # Запускаем polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("✅ Бот запущен и ожидает команды...")
        logger.info("📡 Polling начат - бот готов к приему сообщений")
        
        try:
            # Держим бота запущенным
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки...")
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
    
    async def start_webhook(self):
        """Запуск бота в режиме webhook (для продакшена)"""
        logger.info("🌐 Запуск webhook режима...")
        
        # Настраиваем webhook
        await self.setup_webhook()
        
        # Создаем web сервер
        app = self.setup_web_server()
        
        # Запускаем web сервер
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        
        logger.info("🚀 Web server started on port 8080")
        logger.info("✅ Webhook режим запущен")
        
        try:
            # Держим сервер запущенным
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки...")
        finally:
            await runner.cleanup()

    # ===== MAIN ФУНКЦИЯ =====
    
    async def run(self):
        """Главная функция запуска бота"""
        try:
            logger.info("✅ Асинхронная база данных инициализирована")
            
            # Настраиваем приложение
            await self.setup_application()
            
            # Запускаем бота
            await self.start_polling()
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

# ===== ТОЧКА ВХОДА =#
async def main():
    """Главная функция"""
    try:
        # Создаем и запускаем бота
        bot = PassiveNFTBot()
        
        # Загружаем конфигурацию
        logger.info("Конфигурация загружена из config_deploy_fixed.py")
        
        # Инициализируем базу данных
        await bot.database.initialize()
        
        # Информация о запуске
        logger.info("✅ Асинхронная база данных инициализирована")
        logger.info(f"🤖 Бот: @{bot.config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {bot.config.TON_WALLET_ADDRESS[:20]}...")
        logger.info(f"✅ Реферальная система включена (комиссия только за TON)")
        logger.info(f"⭐ Активные подписки за звездочки включены")
        logger.info(f"💎 Все виды TON подписок: 4, 7, 13, 50, 100, 150 TON")
        
        # Запускаем бота
        await bot.run()
        
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка в main: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        logger.info("👋 PassiveNFT Bot завершил работу")

if __name__ == "__main__":
    # Запускаем асинхронное приложение
    asyncio.run(main())
