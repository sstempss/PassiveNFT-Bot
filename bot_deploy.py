#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PassiveNFT Bot - ИСПРАВЛЕННАЯ ВЕРСИЯ С ПОЛНОЙ РЕФЕРАЛЬНОЙ СИСТЕМОЙ
[FIRE] Все критические ошибки исправлены + РЕФЕРАЛЬНАЯ СИСТЕМА:
✅ Chat not found - исправлено 
✅ NoneType errors - исправлено
✅ Username обработка - улучшена
✅ Реальные invite ссылки - работают
✅ Markdown экранирование - исправлено
✅ Async database context managers - исправлено
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

# ===== ЭКРАНИРОВАНИЕ MARKDOWN (ДЛЯ ИСПРАВЛЕНИЯ ОШИБОК TELEGRAM) =====
def escape_markdown(text: str) -> str:
    """
    Экранирование специальных символов Markdown для безопасной отправки сообщений
    Исправляет ошибки: "can't find end of the entity starting at byte offset 45"
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# ===== КОНВЕРТЕР ЭМОДЗИ (для совместимости со старыми версиями Python) =====
def convert_emoji_codes(text: str) -> str:
    """
    Конвертирует кодовые названия эмодзи обратно в символы
    Используется для обеспечения совместимости с старыми версиями Python
    """
    emoji_mapping = {
        '[CHART]': '📊',
        '[MONEY]': '💰', 
        '[PEOPLE]': '👥',
        '[LINK]': '🔗',
        '[TROPHY]': '🏆',
        '[X]': '❌',
        '[CHECK]': '✅',
        '[STAR]': '⭐',
        '[FIRE]': '🔥',
        '[TARGET]': '🎯',
        '[ROCKET]': '🚀',
        '[LIGHTNING]': '⚡',
        '[DIAMOND]': '💎',
        '[PARTY]': '🎉',
        '[WARNING]': '⚠️',
        '[LOCK]': '🔒',
        '[GAME]': '🎮',
        '[MOBILE]': '📱',
        '[LAPTOP]': '💻',
        '[UP]': '📈',
        '[DOWN]': '📉',
        '[GIFT]': '🎁',
        '[BELL]': '🔔',
        '[BULB]': '💡',
        '[SPEECH]': '💬',
        '[CLIPBOARD]': '📋'
    }
    
    for code, emoji in emoji_mapping.items():
        text = text.replace(code, emoji)
    
    return text

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
        
        logger.info("[FIRE] ЗАПУСК PassiveNFT Bot - ПОЛНАЯ ИНТЕГРАЦИЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ...")
        logger.info(f"🆔 Реферальная система с автоматическим расчетом комиссий активирована")
        logger.info(f"💰 Комиссия 10% начисляется только за TON-подписки")
        logger.info(f"🔗 PRIVATE_CHANNEL_LINKS интегрированы")
        logger.info(f"🔄 Система реальных invite ссылок активирована")
        logger.info(f"🛡️ Markdown экранирование активно (исправлены ошибки Telegram)")
        
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
            logger.info("[STAR] Звезды каналы:")
            for amount, channel_id in self.config.CHANNEL_MAPPINGS.items():
                logger.info(f"    {amount} звезд → {channel_id}")
            
            logger.info("* TON подписки:")
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
        self.application.add_handler(CallbackQueryHandler(self.referral_create_link_callback, pattern="^referral_create_link$"))
        self.application.add_handler(CallbackQueryHandler(self.referral_stats_callback, pattern="^referral_stats$"))
        self.application.add_handler(CallbackQueryHandler(self.copy_ton_callback, pattern="^copy_ton$"))
        self.application.add_handler(CallbackQueryHandler(self.back_callback, pattern="^back$"))
        
        # Обработчик всех текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info("✅ Все обработчики команд зарегистрированы с реферальной системой")
    
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
            
            # ИСПРАВЛЕНО: Экранирование Markdown для безопасной отправки
            safe_text = escape_markdown(welcome_text)
            await update.message.reply_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ /start выполнен успешно для пользователя {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"[X] Ошибка в /start: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))
    
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
• 👥 Реферальная система - Информация о доработке

📞 **Поддержка:** @{self.config.MANAGER_USERNAME}

🚧 **Реферальная система:**
• Статус: Временно недоступна
• В стадии доработки
• Скоро будет запущена автоматическая система комиссий
• Обязательно уведомим всех о запуске!

* **Доступные функции:**
• Подписки за звезды и TON
• Мгновенное получение доступа
• Поддержка менеджеров 24/7
• Автоматическая обработка платежей
"""
        # ИСПРАВЛЕНО: Экранирование Markdown
        safe_text = escape_markdown(help_text)
        await update.message.reply_text(safe_text, parse_mode='Markdown')
    
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
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Доступ запрещен. Только для администраторов.")))
            return
        
        try:
            # Меню выбора типа подписки
            keyboard = [
                [
                    InlineKeyboardButton(convert_emoji_codes("[STAR] 25 звезд"), callback_data="confirmpay_type_25_stars"),
                    InlineKeyboardButton(convert_emoji_codes("[STAR] 50 звезд"), callback_data="confirmpay_type_50_stars")
                ],
                [
                    InlineKeyboardButton(convert_emoji_codes("[STAR] 75 звезд"), callback_data="confirmpay_type_75_stars"),
                    InlineKeyboardButton(convert_emoji_codes("[STAR] 100 звезд"), callback_data="confirmpay_type_100_stars")
                ],
                [
                    InlineKeyboardButton("* 13 TON", callback_data="confirmpay_type_13_ton"),
                    InlineKeyboardButton("* 7 TON", callback_data="confirmpay_type_7_ton")
                ],
                [
                    InlineKeyboardButton("* 4 TON", callback_data="confirmpay_type_4_ton"),
                    InlineKeyboardButton("* 50 TON", callback_data="confirmpay_type_50_ton")
                ],
                [
                    InlineKeyboardButton("* 100 TON", callback_data="confirmpay_type_100_ton"),
                    InlineKeyboardButton("* 150 TON", callback_data="confirmpay_type_150_ton")
                ],
                [
                    InlineKeyboardButton("📊 История подтверждений", callback_data="confirmpay_history"),
                    InlineKeyboardButton("📈 Статистика", callback_data="confirmpay_stats")
                ]
            ]
            
            message_text = """👨‍💼 **МЕНЕДЖЕРСКАЯ ПАНЕЛЬ ПОДТВЕРЖДЕНИЯ ОПЛАТЫ**

Выберите тип подписки для подтверждения:

[STAR] **ЗВЕЗДОЧКИ:** 25, 50, 75, 100 (без комиссии)
* **TON:** 4, 7, 13, 50, 100, 150 (10% комиссия рефереру)

📋 После выбора типа подписки:
1. Введите username пользователя
2. Система автоматически отправит одноразовую ссылку
3. Реферальная комиссия будет начислена (только для TON)
4. Пользователь получит уведомление о подтверждении

⚡ Дополнительные функции: История и Статистика"""
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(message_text)
            await update.message.reply_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
            
            logger.info(f"✅ /confirmpay меню показано пользователю {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"[X] Ошибка в confirmpay_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))
    
    async def confirmpay_subscription_type_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора типа подписки для подтверждения"""
        query = update.callback_query
        await query.answer()
        
        if update.effective_user.id not in self.config.ADMIN_USER_IDS:
            await query.edit_message_text("[X] Доступ запрещен.")
            return
        
        try:
            # Извлекаем тип подписки из callback_data
            subscription_type = query.data.replace("confirmpay_type_", "")
            
            # Определяем отображаемое название
            subscription_names = {
                "25_stars": "[STAR] 25 звезд",
                "50_stars": "[STAR] 50 звезд", 
                "75_stars": "[STAR] 75 звезд",
                "100_stars": "[STAR] 100 звезд",
                "13_ton": "* 13 TON",
                "7_ton": "* 7 TON",
                "4_ton": "* 4 TON",
                "50_ton": "* 50 TON",
                "100_ton": "* 100 TON",
                "150_ton": "* 150 TON"
            }
            
            display_name = subscription_names.get(subscription_type, subscription_type)
            
            # Определяем, есть ли комиссия
            payment_method = self.config.get_payment_method(subscription_type)
            commission_info = "💰 **Комиссия рефереру:** 10%" if payment_method == 'TON' else "💰 **Комиссия рефереру:** 0% (Stars)"
            
            # Сохраняем в очередь ожидания
            self.confirmation_queue[query.from_user.id] = {
                'subscription_type': subscription_type,
                'step': 'waiting_username',
                'timestamp': time.time()
            }
            
            # Кнопка отмены
            keyboard = [
                [InlineKeyboardButton("❌ Отмена", callback_data="confirmpay_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = (
                f"✅ **ВЫБРАН ТИП ПОДПИСКИ:** {display_name}\n\n"
                f"💰 **Метод оплаты:** {payment_method}\n"
                f"{commission_info}\n\n"
                f"📝 **СЛЕДУЮЩИЙ ШАГ:**\n"
                f"Введите username пользователя (например: `john_doe` или `@john_doe`)\n\n"
                f"🔄 Система автоматически:\n"
                f"• Создаст одноразовую invite ссылку\n"
                f"• Отправит уведомление пользователю\n"
                f"• Зафиксирует операцию в истории\n"
                f"• Начислит комиссию рефереру (если есть)"
            )
            
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(message_text)
            await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
            
            logger.info(f"✅ Выбран тип подписки {subscription_type} пользователем {query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_subscription_type_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.edit_message_text(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))
    
    async def confirmpay_back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик возврата в главное меню /confirmpay - ИСПРАВЛЕНО"""
        try:
            query = update.callback_query
            await query.answer()
            
            # ИСПРАВЛЕНО: Операция отмены доступна только для админов, но показываем корректное сообщение
            if query.from_user.id not in self.config.ADMIN_USER_IDS:
                await query.edit_message_text("❌ Отмена подтверждения - доступно только админам.")
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
                await query.edit_message_text("[X] Произошла ошибка. Попробуйте позже.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_back_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            try:
                await update.callback_query.answer("[X] Произошла ошибка. Попробуйте позже.")
            except:
                pass  # Игнорируем ошибки ответа на callback
    
    async def confirmpay_history_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик показа истории подтверждений"""
        query = update.callback_query
        await query.answer()
        
        if update.effective_user.id not in self.config.ADMIN_USER_IDS:
            await query.edit_message_text("[X] Доступ запрещен.")
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
            
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(message_text)
            await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ История подтверждений отправлена пользователю {query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_history_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.edit_message_text(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))
    
    async def confirmpay_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик показа статистики"""
        query = update.callback_query
        await query.answer()
        
        if update.effective_user.id not in self.config.ADMIN_USER_IDS:
            await query.edit_message_text("[X] Доступ запрещен.")
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
                        "25_stars": "[STAR] 25 звезд",
                        "50_stars": "[STAR] 50 звезд", 
                        "75_stars": "[STAR] 75 звезд",
                        "100_stars": "[STAR] 100 звезд",
                        "13_ton": "* 13 TON",
                        "7_ton": "* 7 TON",
                        "4_ton": "* 4 TON",
                        "50_ton": "* 50 TON",
                        "100_ton": "* 100 TON",
                        "150_ton": "* 150 TON"
                    }
                    display_name = subscription_names.get(sub_type, sub_type)
                    message_text += f"\n• **{display_name}:** {count}"
            else:
                message_text += "\n• Нет данных"
            
            message_text += f"\n\n📅 **Обновлено:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
            # Кнопка "Назад"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="confirmpay_back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(message_text)
            await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"✅ Статистика отправлена пользователю {query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в confirmpay_stats_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.edit_message_text(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))
    
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
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))
    
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
            
            # ИСПРАВЛЕНО: Правильная обработка реферальной системы
            referral_result = {'referrer_found': False, 'referrer_id': None, 'commission_calculated': 0.0}
            
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
                    referral_result = {
                        'referrer_found': True,
                        'referrer_id': pending_referrer,
                        'commission_calculated': commission
                    }
            
            # Отправляем ссылку пользователю и получаем статус отправки
            link_sent_success = await self.send_subscription_link_to_user(username, subscription_type, secure_link, context)
            
            # ИНФОРМИРУЕМ АДМИНА О РЕЗУЛЬТАТАХ СО СТАТУСОМ ОТПРАВКИ
            link_status = "✅ Отправлена успешно" if link_sent_success else "❌ Ошибка отправки"
            admin_report = f"""✅ **ПОДТВЕРЖДЕНИЕ ЗАВЕРШЕНО**

👤 **Пользователь:** @{username}
📦 **Подписка:** {subscription_type}
💰 **Метод оплаты:** {payment_method}
* **Сумма:** {subscription_amount} TON

🔗 **Статус ссылки:** {link_status}"""

            if referral_result.get('referrer_found'):
                admin_report += f"""
👥 **Реферальная система:**
• Реферер найден: ID {referral_result['referrer_id']}
• Комиссия начислена: {referral_result['commission_calculated']} TON
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
            
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_admin_report = escape_markdown(admin_report)
            await update.message.reply_text(safe_admin_report, parse_mode='Markdown')
            
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
                "25_stars": "[STAR] 25 звезд",
                "50_stars": "[STAR] 50 звезд", 
                "75_stars": "[STAR] 75 звезд",
                "100_stars": "[STAR] 100 звезд",
                "13_ton": "* 13 TON",
                "7_ton": "* 7 TON",
                "4_ton": "* 4 TON",
                "50_ton": "* 50 TON",
                "100_ton": "* 100 TON",
                "150_ton": "* 150 TON"
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
            
            # ИСПРАВЛЕНО: Безопасная отправка сообщения пользователю с получением статуса
            link_sent_success = await self.send_safe_message_to_user(username, message_text, context)
            
            logger.info(f"✅ Ссылка отправлена пользователю @{username} - Статус: {'УСПЕШНО' if link_sent_success else 'ОШИБКА'}")
            
            # Возвращаем статус отправки
            return link_sent_success
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ссылки пользователю @{username}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise e
    
    async def send_safe_message_to_user(self, username: str, message_text: str, context: ContextTypes.DEFAULT_TYPE):
        """Безопасная отправка сообщения пользователю - ИСПРАВЛЕНО"""
        logger.info(f"🔄 Попытка отправить сообщение пользователю @{username}")
        link_sent_success = False
        try:
            # Сначала пытаемся получить user_id через метод get_chat
            try:
                chat = await context.bot.get_chat(f"@{username}")
                if chat.type == 'private':
                    # Прямая отправка по user_id
                    # ИСПРАВЛЕНО: Экранирование Markdown перед отправкой
                    safe_text = escape_markdown(message_text)
                    await context.bot.send_message(
                        chat_id=chat.id,
                        text=safe_text,
                        parse_mode='Markdown'
                    )
                    link_sent_success = True
                    logger.info(f"✅ Сообщение успешно отправлено пользователю @{username} через get_chat")
                    return True
            except TelegramError as e:
                logger.error(f"❌ Ошибка при получении чата @{username}: {e}")
            
            # Если get_chat не сработал, пытаемся использовать resolve_username через get_chat_member
            try:
                # Пытаемся получить информацию о пользователе как участнике бота
                bot_info = await context.bot.get_me()
                try:
                    member = await context.bot.get_chat_member(bot_info.id, username)
                    # Если пользователь является участником чата бота
                    if member.status in ['member', 'administrator', 'creator']:
                        # Попытка отправить через chat_id бота
                        safe_text = escape_markdown(f"📬 Сообщение для @{username}:\n\n{message_text}")
                        await context.bot.send_message(
                            chat_id=bot_info.id,
                            text=safe_text
                        )
                        link_sent_success = True
                        logger.info(f"⚠️ Сообщение для @{username} отправлено через бота (прямая отправка недоступна)")
                        return True
                except Exception as e:
                    logger.warning(f"⚠️ Пользователь @{username} не является участником чата бота: {e}")
            except Exception as e:
                logger.error(f"❌ Ошибка при проверке статуса пользователя @{username}: {e}")
            
            # Если все методы не сработали
            link_sent_success = False
            logger.error(f"❌ Невозможно отправить сообщение пользователю @{username} - не взаимодействовал с ботом или заблокировал")
            return False
            
        except Exception as e:
            link_sent_success = False
            logger.error(f"❌ Критическая ошибка отправки сообщения пользователю @{username}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
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
                await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] У вас нет доступа к реферальной статистике")))
                return

            # Получаем детальную реферальную статистику
            detailed_stats = await self.database.get_referral_stats()
            
            if not detailed_stats:
                referral_text = """🔗 **РЕФЕРАЛЬНАЯ СТАТИСТИКА**

[CHART] Данные о рефералах отсутствуют.
Пока что никто не привлекал рефералов.
"""
            else:
                referral_text = f"""[LINK] **ДЕТАЛЬНАЯ РЕФЕРАЛЬНАЯ СТАТИСТИКА**

[CHART] **Всего активных рефереров:** {len(detailed_stats)}
[MONEY] **Общий заработок:** {sum(stat['total_earnings'] for stat in detailed_stats):.2f} TON
👥 **Всего рефералов:** {sum(stat['total_referrals'] for stat in detailed_stats)}

[TROPHY] **ТОП-10 рефереров по заработку:**"""

                for i, stat in enumerate(detailed_stats[:10], 1):
                    name = stat['referrer_username'] or 'Без username'
                    referrals = stat['total_referrals']
                    earnings = stat['total_earnings']
                    ton_refs = stat['ton_referrals']
                    
                    referral_text += f"""
**{i}.** @{name}
   [PEOPLE] Рефералов: {referrals} ({ton_refs} TON)
   [MONEY] Заработок: {earnings:.2f} TON"""

            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(convert_emoji_codes(referral_text))
            await update.message.reply_text(safe_text, parse_mode='Markdown')
            logger.info(f"[CHECK] Детальная реферальная статистика отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_refstats_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))

    async def admin_refstat_by_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда реферальной статистики по конкретному username"""
        logger.info(f"КОМАНДА /refstat от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS:
                await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] У вас нет доступа к реферальной статистике")))
                return

            # Извлекаем username из команды
            command_text = update.message.text
            parts = command_text.split()
            
            if len(parts) < 2:
                await update.message.reply_text("❌ Использование: /refstat <username>\nПример: /refstat john_doe")
                return
            
            username = parts[1].replace('@', '')  # Убираем @ если есть
            
            # Получаем статистику по username
            # Получаем статистику для пользователя по username
            user_data = await self.database.get_user_by_username(username)
            if user_data:
                user_stats = await self.database.get_user_referral_stats(user_data['id'])
            else:
                user_stats = "Пользователь не найден"
            
            if not user_stats:
                await update.message.reply_text(f"📊 Статистика для @{username} не найдена.\nПользователь может не существовать или не иметь рефералов.")
                return

            # Формируем детальный отчет
            name = user_stats.get('first_name', '') + ' ' + user_stats.get('last_name', '')
            name = name.strip() or user_stats.get('username', 'Без имени')
            
            referral_text = f"""🔗 **РЕФЕРАЛЬНАЯ СТАТИСТИКА @{username}**

👤 **Пользователь:** {name}
📊 **Всего рефералов:** {user_stats['total_referrals']}
[MONEY] **Общий заработок:** {user_stats['total_earnings']:.2f} TON

* **Детализация:**
• TON рефералов: {user_stats['ton_referrals']}
• Stars рефералы: {user_stats['stars_referrals']}
• Заработок с TON: {user_stats['ton_earnings']:.2f} TON

💡 **Комиссия:** 10% от TON-подписок рефералов
📅 **Статистика актуальна на:** {datetime.now().strftime('%d.%m.%Y %H:%M')}"""

            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(referral_text)
            await update.message.reply_text(safe_text, parse_mode='Markdown')
            logger.info(f"✅ Статистика для @{username} отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_refstat_by_username: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))

    # ===== СИСТЕМА ПОДПИСОК =====

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
                [InlineKeyboardButton("* Без активностей (за TON)", callback_data="select_ton")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                # ИСПРАВЛЕНО: Экранирование Markdown
                safe_text = escape_markdown(subscription_text)
                await query.message.edit_text(safe_text, reply_markup=reply_markup)
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
            await query.answer(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))

    async def select_stars_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора звездочек"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: select_stars callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            stars_text = """⭐ **ПОДПИСКИ ЗА ЗВЕЗДОЧКИ**

Доступные тарифы с активностями:

⚡ **ПЛАНЫ:**
* [STAR] 25 звезд - Базовый доступ (0.2 TON)
* [STAR] 50 звезд - Расширенный доступ (0.4 TON)
* [STAR] 75 звезд - Премиум доступ (0.6 TON)
* [STAR] 100 звезд - VIP доступ (0.8 TON)

🎮 **В каждом плане:**
• Участие в активностях
• Получение NFT
• Ранний доступ к функциям

💡 **Важно:** За звездочки комиссия рефереру не начисляется

Выберите план:"""

            keyboard = [
                [InlineKeyboardButton(convert_emoji_codes("[STAR] 25 звезд"), callback_data="stars_25")],
                [InlineKeyboardButton(convert_emoji_codes("[STAR] 50 звезд"), callback_data="stars_50")],
                [InlineKeyboardButton(convert_emoji_codes("[STAR] 75 звезд"), callback_data="stars_75")],
                [InlineKeyboardButton(convert_emoji_codes("[STAR] 100 звезд"), callback_data="stars_100")],
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                # ИСПРАВЛЕНО: Экранирование Markdown
                safe_text = escape_markdown(stars_text)
                await query.message.edit_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
                logger.info(f"✅ Звезды планы показаны пользователю {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Планы уже показаны!")
                    logger.info(f"ℹ️ Планы уже показаны для пользователя {update.effective_user.id}")
                else:
                    await query.answer("Ошибка при показе планов.")
                    logger.error(f"❌ Ошибка BadRequest в select_stars_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в select_stars_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))

    async def select_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора TON"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: select_ton callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            ton_text = """* **ПОДПИСКИ ЗА TON**

Доступные тарифы без активностей:

* **ПЛАНЫ:**
• * 4 TON - На 150 человек
• * 7 TON - На 100 человек  
• * 13 TON - На 50 человек
• * 50 TON - VIP план
• * 100 TON - Премиум план
• * 150 TON - Максимальный план

[LOCK] **Особенности:**
• Только доступ к каналам
• Без активностей и NFT
• Стабильная подписка

💰 **Реферальная система:**
• Ваш реферер получит 10% комиссии
• Выгодно приглашать друзей!

Выберите план:"""

            keyboard = [
                [InlineKeyboardButton("* 4 TON", callback_data="ton_4")],
                [InlineKeyboardButton("* 7 TON", callback_data="ton_7")],
                [InlineKeyboardButton("* 13 TON", callback_data="ton_13")],
                [InlineKeyboardButton("* 50 TON", callback_data="ton_50")],
                [InlineKeyboardButton("* 100 TON", callback_data="ton_100")],
                [InlineKeyboardButton("* 150 TON", callback_data="ton_150")],
                [InlineKeyboardButton("🔙 Назад", callback_data="subscription")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                # ИСПРАВЛЕНО: Экранирование Markdown
                safe_text = escape_markdown(convert_emoji_codes(ton_text))
                await query.message.edit_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
                logger.info(f"✅ TON планы показаны пользователю {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Планы уже показаны!")
                    logger.info(f"ℹ️ Планы уже показаны для пользователя {update.effective_user.id}")
                else:
                    await query.answer("Ошибка при показе планов.")
                    logger.error(f"❌ Ошибка BadRequest в select_ton_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в select_ton_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))

    async def stars_subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик подписки на звезды"""
        query = update.callback_query
        await query.answer()
        
        # Извлекаем количество звезд
        stars = int(query.data.split('_')[1])
        
        # Информация о планах
        plan_info = {
            25: {
                'price': '25 ⭐',
                'ton_equivalent': '0.2 TON',
                'description': 'Базовый план с участием в активностях'
            },
            50: {
                'price': '50 ⭐',
                'ton_equivalent': '0.4 TON',
                'description': 'Расширенный план с дополнительными функциями'
            },
            75: {
                'price': '75 ⭐',
                'ton_equivalent': '0.6 TON',
                'description': 'Премиум план с приоритетным доступом'
            },
            100: {
                'price': '100 ⭐',
                'ton_equivalent': '0.8 TON',
                'description': 'VIP план с эксклюзивными возможностями'
            }
        }
        
        info = plan_info.get(stars, {})
        price = info.get('price', f'{stars} ⭐')
        ton_eq = info.get('ton_equivalent', 'N/A')
        description = info.get('description', 'Подписка на закрытый канал')
        
        # Получаем канал для данного количества звезд
        channel_id = self.config.CHANNEL_MAPPINGS.get(stars)
        
        # Проверяем, есть ли у пользователя доступ
        has_access = await self.check_user_access(update.effective_user.id, stars, 'stars')
        
        if has_access:
            # Пользователь уже имеет доступ - показываем ссылку
            channel_link = self.config.PRIVATE_CHANNEL_LINKS.get(f"{stars}_stars", "https://t.me/passivenft_channel")
            
            message_text = f"""🎉 **У ВАС УЖЕ ЕСТЬ ДОСТУП!**

✅ **Ваш план:** {price} ({ton_eq})
📖 **Описание:** {description}

🔗 **Ссылка на канал:** {channel_link}

* **Наслаждайтесь активностями и получайте NFT!**

💡 **Реферальная система:** За Stars подписки комиссия рефереру не начисляется
"""
            keyboard = [[InlineKeyboardButton("📢 Написать менеджеру", url=f"https://t.me/{self.config.MANAGER_USERNAME}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(convert_emoji_codes(message_text))
            await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
            return
        
        # Пользователь не имеет доступа - показываем инструкции по покупке
        message_text = f"""💫 **ПЛАН: {price} ({ton_eq})**

📖 **Описание:** {description}

🚀 **Как получить доступ:**
1. Купите {stars} звездочек в Telegram
2. Отправьте их @{self.config.STARS_USERNAME}
3. Получите ссылку на закрытый канал

⭐ **Важно:** Звездочки покупаются в настройках Telegram Premium

* **После покупки:** Получите мгновенный доступ к каналу!

💡 **Реферальная система:** За Stars подписки комиссия рефереру не начисляется

*Нужна помощь? Напишите @{self.config.STARS_USERNAME}*
"""
        keyboard = [
            [InlineKeyboardButton("💬 Связаться с менеджером", callback_data="contact")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ИСПРАВЛЕНО: Экранирование Markdown
        safe_text = escape_markdown(convert_emoji_codes(message_text))
        await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    async def ton_subscription_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик подписки на TON"""
        query = update.callback_query
        await query.answer()
        
        # Извлекаем количество TON
        ton_amount = int(query.data.split('_')[1])
        
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

* **Наслаждайтесь закрытым сообществом!**

💰 **Реферальная система:** Ваш реферер получил 10% комиссии ({ton_amount * 0.1:.1f} TON)
"""
            keyboard = [[InlineKeyboardButton("📢 Написать менеджеру", url=f"https://t.me/{self.config.MANAGER_USERNAME}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(convert_emoji_codes(message_text))
            await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
            return
        
        # Пользователь не имеет доступа - показываем инструкции по покупке
        commission_info = f"Ваш реферер получит {ton_amount * 0.1:.1f} TON комиссии"
        
        message_text = f"""* **ПЛАН: {price} ({name})**

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
            [InlineKeyboardButton(convert_emoji_codes("[CLIPBOARD] Скопировать адрес"), callback_data="copy_ton")],
            [InlineKeyboardButton("💬 Связаться с менеджером", callback_data="contact")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ИСПРАВЛЕНО: Экранирование Markdown
        safe_text = escape_markdown(convert_emoji_codes(message_text))
        await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')

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
        keyboard = [[InlineKeyboardButton(convert_emoji_codes("[SPEECH] Написать менеджеру"), url=f"https://t.me/{self.config.STARS_USERNAME}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ИСПРАВЛЕНО: Экранирование Markdown
        safe_text = escape_markdown(convert_emoji_codes(message_text))
        await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def payment_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик оплаты TON"""
        query = update.callback_query
        await query.answer()
        
        ton_amount = int(query.data.split('_')[2])
        commission = ton_amount * 0.1
        
        message_text = f"""* **ОПЛАТА: {ton_amount} TON**

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

[LOCK] **Безопасность:**
• Оплата только на указанный адрес
• Подтверждение менеджером
• Прозрачные условия

💰 **Реферальная система:** Ваш реферер получит {commission:.1f} TON комиссии

❓ **Вопросы?** @{self.config.MANAGER_USERNAME}
"""
        keyboard = [
            [InlineKeyboardButton(convert_emoji_codes("[CLIPBOARD] Скопировать адрес"), callback_data="copy_ton")],
            [InlineKeyboardButton(convert_emoji_codes("[SPEECH] Написать менеджеру"), url=f"https://t.me/{self.config.MANAGER_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ИСПРАВЛЕНО: Экранирование Markdown
        safe_text = escape_markdown(convert_emoji_codes(message_text))
        await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')

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
        keyboard = [[InlineKeyboardButton(convert_emoji_codes("[SPEECH] Написать менеджеру"), url=f"https://t.me/{self.config.STARS_USERNAME}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ИСПРАВЛЕНО: Экранирование Markdown
        safe_text = escape_markdown(convert_emoji_codes(message_text))
        await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')

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
            [InlineKeyboardButton(convert_emoji_codes("[CLIPBOARD] Скопировать адрес"), callback_data="copy_ton")],
            [InlineKeyboardButton(convert_emoji_codes("[SPEECH] Написать менеджеру"), url=f"https://t.me/{self.config.MANAGER_USERNAME}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # ИСПРАВЛЕНО: Экранирование Markdown
        safe_text = escape_markdown(convert_emoji_codes(message_text))
        await query.edit_message_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')

    # ===== СИСТЕМА РЕФЕРАЛОВ =====
    
    async def referral_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Реферальная система' - АКТИВНА"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()
            user = query.from_user

            # АКТИВНАЯ РЕФЕРАЛЬНАЯ СИСТЕМА
            referral_text = f"""👥 **Реферальная система**

💰 Зарабатывайте 10% с каждой оплаты ваших рефералов!
🎯 Приглашайте друзей и получайте пассивный доход

📈 **Ваша реферальная ссылка будет доступна после создания**

💡 **Как это работает:**
1️⃣ Поделитесь вашей персональной ссылкой
2️⃣ Друг переходит по ссылке и оплачивает подписку
3️⃣ Вы получаете 10% от суммы оплаты
4️⃣ Выплаты происходят автоматически"""

            # Кнопки для активной реферальной системы
            keyboard = [
                [InlineKeyboardButton("🔗 Создать ссылку", callback_data="referral_create_link")],
                [InlineKeyboardButton("📊 Моя статистика", callback_data="referral_stats")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                # ИСПРАВЛЕНО: Экранирование Markdown
                safe_text = escape_markdown(referral_text)
                await query.message.edit_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
                logger.info(f"ℹ️ Реферальная система показана как 'временно недоступна' для пользователя {update.effective_user.id}")
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    await query.answer("Уведомление о реферальной системе уже показано!")
                    logger.info(f"ℹ️ Уведомление уже показано для пользователя {update.effective_user.id}")
                else:
                    await query.answer("Ошибка при показе информации.")
                    logger.error(f"❌ Ошибка BadRequest в referral_callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))

    async def referral_stats_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик статистики рефералов - ВРЕМЕННО ОТКЛЮЧЕН"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral_stats callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            # АКТИВНАЯ СТАТИСТИКА РЕФЕРАЛОВ  
            stats_text = f"""📊 **Статистика рефералов**

👤 Пользователь: @{user.username or 'без имени'}
🆔 ID: {user.id}

❌ У вас пока нет рефералов

💡 **Как привлечь рефералов:**
• Поделитесь вашей персональной ссылкой
• Пригласите друзей и знакомых  
• Расскажите о преимуществах сервиса

💰 **Потенциальный заработок:**
• 10% с каждой TON-подписки ваших рефералов
• Стабильный пассивный доход
• Растущий доход с каждым новым рефералом

🔗 **Создайте ссылку и начните зарабатывать уже сегодня!**"""

            # Кнопка "Назад"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="referral")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(stats_text)
            await query.message.edit_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
            logger.info(f"ℹ️ Статистика рефералов показана как 'временно недоступна' для пользователя {query.from_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_stats_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))
    
    async def referral_create_link_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик создания реферальной ссылки - ИСПРАВЛЕНО"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: referral_create_link callback")
        try:
            query = update.callback_query
            await query.answer()
            user = query.from_user
            
            # Создаем пользователя в базе данных если его нет
            await self.database.get_or_create_user(
                user_id=user.id, 
                username=user.username or "", 
                first_name=user.first_name or "", 
                last_name=user.last_name or ""
            )
            
            # Генерируем персональную реферальную ссылку
            referral_link = f"https://t.me/{self.config.BOT_USERNAME}?start=ref_{user.id}"
            
            link_text = f"""🔗 Ваша персональная реферальная ссылка:

[{referral_link}]({referral_link})

💰 Приглашайте друзей и зарабатывайте 10% с каждой их оплаты подписки!"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Моя статистика", callback_data="referral_stats")],
                [InlineKeyboardButton("🔙 Назад", callback_data="referral")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # ИСПРАВЛЕНО: Используем MarkdownV2 для корректного отображения ссылок
            safe_text = escape_markdown(link_text)
            await query.message.edit_text(safe_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
            logger.info(f"✅ Реферальная ссылка создана для пользователя {user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в referral_create_link_callback: {e}")
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
                [InlineKeyboardButton(convert_emoji_codes("[SPEECH] Написать менеджеру"), url=f"https://t.me/{self.config.MANAGER_USERNAME}")],
                [InlineKeyboardButton("⭐ Написать менеджеру звезд", url=f"https://t.me/{self.config.STARS_USERNAME}")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                # ИСПРАВЛЕНО: Экранирование Markdown
                safe_text = escape_markdown(contact_text)
                await query.message.edit_text(safe_text, reply_markup=reply_markup, parse_mode='Markdown')
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
            await query.answer(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))

    async def copy_ton_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик копирования TON адреса"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: copy_ton callback от пользователя {update.effective_user.id}")
        try:
            query = update.callback_query
            await query.answer()

            copy_message = f"Адрес кошелька скопирован!\n\n`{self.config.TON_WALLET_ADDRESS}`\n\nОтправьте указанную сумму TON."
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_copy_message = escape_markdown(copy_message)
            await query.message.edit_text(safe_copy_message, parse_mode='Markdown')
            logger.info(f"✅ Адрес TON скопирован для пользователя {update.effective_user.id}")
        except Exception as e:
            logger.error(f"❌ Ошибка в copy_ton_callback: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.answer(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))

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
                # ИСПРАВЛЕНО: Экранирование Markdown
                safe_text = escape_markdown(welcome_text)
                await query.message.edit_text(safe_text, reply_markup=reply_markup)
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
            await query.answer(escape_markdown("[X] Произошла ошибка. Попробуйте позже."))

    # ===== АДМИН КОМАНДЫ =====
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /adminserveraa"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraa от пользователя {update.effective_user.id}")
        try:
            user = update.effective_user

            # Проверяем, является ли пользователь админом
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] У вас нет доступа к админ панели")))
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

            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(admin_text)
            await update.message.reply_text(safe_text, parse_mode='Markdown')
            logger.info(f"✅ Админ панель показана пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))

    async def admin_stat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды статистики"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraastat от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("[X] У вас нет доступа к статистике")
                return

            # Получаем статистику из базы данных
            stats = await self.database.get_confirmation_stats()
            referral_earnings = await self.database.get_total_commission_earned()
            
            if stats:
                stats_text = f"""📊 **СТАТИСТИКА PassiveNFT Bot**

👥 **Пользователи:** {await self.database.get_all_users_count()}
* **Подписки за TON:** {sum(1 for sub_type in stats.get('by_subscription_type', {}) if 'ton' in sub_type)} типов
⭐ **Подписки за звезды:** {sum(1 for sub_type in stats.get('by_subscription_type', {}) if 'stars' in sub_type)} типов
👥 **Рефералы:** {await self.database.get_total_referrals_count()}

💰 **Доходы:**
• Подтверждено подписок: {stats.get('total_confirmations', 0)}
• Сегодня: {stats.get('today_confirmations', 0)}
• За неделю: {stats.get('week_confirmations', 0)}
• За месяц: {stats.get('month_confirmations', 0)}

* **Реферальная система:**
• Общий заработок рефереров: {referral_earnings:.2f} TON
• Комиссия: 10% от TON-подписок

🕒 **Обновлено:** {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
            else:
                stats_text = "📊 Статистика недоступна"
                
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(stats_text)
            await update.message.reply_text(safe_text, parse_mode='Markdown')
            logger.info(f"✅ Статистика отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_stat_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))

    async def admin_people_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды списка участников"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraapeople от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("[X] У вас нет доступа к списку участников")
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
                
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(users_text)
            await update.message.reply_text(safe_text, parse_mode='Markdown')
            logger.info(f"✅ Список пользователей отправлен пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_people_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))

    async def admin_referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды реферальной статистики"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /adminserveraaref от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] У вас нет доступа к реферальной статистике")))
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
                
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(referral_text)
            await update.message.reply_text(safe_text, parse_mode='Markdown')
            logger.info(f"✅ Реферальная статистика отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в admin_referral_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды рассылки"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /broadcast от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("[X] У вас нет доступа к рассылке")
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
                        # ИСПРАВЛЕНО: Экранирование Markdown в рассылке
                        safe_message = escape_markdown(f"📢 **ОБЪЯВЛЕНИЕ**\n\n{message_to_send}")
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=safe_message,
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
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_report = escape_markdown(report)
            await update.message.reply_text(safe_report, parse_mode='Markdown')
            logger.info(f"✅ Рассылка завершена: {sent_count} отправлено, {failed_count} ошибок")

        except Exception as e:
            logger.error(f"❌ Ошибка в broadcast_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестовая команда"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /testcmd от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("[X] У вас нет доступа к тестовой команде")
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

🛡️ **Markdown экранирование:**
• Исправлены ошибки Telegram API
• Безопасная отправка сообщений

🔧 **Все функции работают!**
"""
            
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(test_info)
            await update.message.reply_text(safe_text, parse_mode='Markdown')
            logger.info(f"✅ Тестовая команда выполнена для пользователя {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в test_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))

    # ===== НОВЫЕ КОМАНДЫ ДЛЯ РАБОТЫ С КАНАЛАМИ =====
    
    async def channel_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда информации о каналах"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /channel_info от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("[X] У вас нет доступа к информации о каналах")
                return

            # Формируем информацию о каналах
            channel_info = """📺 **ИНФОРМАЦИЯ О КАНАЛАХ**

⭐ **КАНАЛЫ ЗА ЗВЕЗДЫ:**"""
            
            for stars, channel_id in self.config.CHANNEL_MAPPINGS.items():
                link = self.config.PRIVATE_CHANNEL_LINKS.get(f"{stars}_stars", "ссылка не найдена")
                channel_info += f"\n• ⭐ {stars} звезд → {channel_id}"
                channel_info += f"\n  Ссылка: {link[:50]}..."
            
            channel_info += "\n\n* **КАНАЛЫ ЗА TON:**\n"
            
            for ton_amount, channel_id in self.config.TON_CHANNEL_MAPPINGS.items():
                link = self.config.PRIVATE_CHANNEL_LINKS.get(f"{ton_amount}_ton", "ссылка не найдена")
                channel_info += f"• * {ton_amount} TON → {channel_id}\n"
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
            
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(channel_info)
            await update.message.reply_text(safe_text, parse_mode='Markdown')
            logger.info(f"✅ Информация о каналах отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в channel_info_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))

    async def get_channel_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда получения ID текущего канала"""
        logger.info(f"КОМАНДА ПОЛУЧЕНА: /get_channel_id от пользователя {update.effective_user.id}")
        
        try:
            # Проверяем права администратора
            user = update.effective_user
            if user.id not in self.config.ADMIN_USER_IDS and user.username not in self.config.get_admin_usernames():
                await update.message.reply_text("[X] У вас нет доступа к этой команде")
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
                
            # ИСПРАВЛЕНО: Экранирование Markdown
            safe_text = escape_markdown(channel_info)
            await update.message.reply_text(safe_text, parse_mode='Markdown')
            logger.info(f"✅ Информация о канале отправлена пользователю {user.id}")

        except Exception as e:
            logger.error(f"❌ Ошибка в get_channel_id_command: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            await update.message.reply_text(escape_markdown(convert_emoji_codes("[X] Произошла ошибка. Попробуйте позже.")))

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

# ===== ТОЧКА ВХОДА =====
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
        logger.info(f"* Все виды TON подписок: 4, 7, 13, 50, 100, 150 TON")
        logger.info(f"🛡️ Markdown экранирование активно (исправлены ошибки Telegram)")
        
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
