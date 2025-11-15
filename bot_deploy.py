"""
Безопасная версия Telegram бота PassiveNFT для деплоя на Railway
Использует переменные окружения вместо прямого хранения секретов
"""
import logging
import json
import sqlite3
from typing import Dict, Any
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from config_deploy_new import *
from database import DatabaseManager

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PassiveNFTBot:
    def __init__(self):
        self.config = type('Config', (), {
            'BOT_TOKEN': BOT_TOKEN,
            'ADMIN_USER_IDS': ADMIN_USER_IDS,
            'TON_WALLET_ADDRESS': TON_WALLET_ADDRESS,
            'MANAGER_USERNAME': MANAGER_USERNAME,
            'BOT_USERNAME': BOT_USERNAME,
            'WELCOME_MESSAGE': WELCOME_MESSAGE,
            'SUBSCRIPTIONS': SUBSCRIPTIONS,
            'CONTACT_MESSAGE': f"📞 **Связь с менеджером**\n\n💬 Обратитесь к @{MANAGER_USERNAME} для вопросов по подписке",
            'REFERRAL_MESSAGE': f"""🔗 **Реферальная система PassiveNFT**

💰 Приглашайте друзей и зарабатывайте 10% с каждой их покупки!

🎯 Как это работает:
• Поделитесь вашей реферальной ссылкой
• Друг регистрируется по ссылке
• Вы получаете 10% с каждой его покупки
• Бонус выплачивается автоматически

📞 **Поддержка:** @{MANAGER_USERNAME}""",
            'DATABASE_PATH': DATABASE_FILE
        })()
        self.db = DatabaseManager(self.config.DATABASE_PATH)
        self.application = Application.builder().token(self.config.BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        # Основные команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("adminserveraa", self.admin_panel))
        
        # Обработчики callback queries
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Обработчики админ команд
        self.application.add_handler(CommandHandler("alminserveraastat", self.admin_stats))
        self.application.add_handler(CommandHandler("adminserveraapeople", self.admin_people))
        self.application.add_handler(CommandHandler("adminserveraaref", self.admin_referrals))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        
        # Получаем или создаем пользователя в БД
        referral_code = self.db.get_or_create_user(
            user.id, 
            user.username or "", 
            user.first_name or "", 
            user.last_name or ""
        )
        
        # Проверяем реферальный код в аргументах
        if update.message and len(update.message.text.split()) > 1:
            ref_code = update.message.text.split()[1]
            if ref_code != referral_code:
                referrer_id = self.db.get_user_by_referral_code(ref_code)
                if referrer_id:
                    # Создаем реферальную связь
                    await self.create_referral(referrer_id, user.id, ref_code)
        
        # Отправляем приветственное сообщение
        keyboard = [
            [InlineKeyboardButton("💎 Подписки", callback_data="subscriptions")],
            [InlineKeyboardButton("📞 Связь с менеджером", callback_data="contact")],
            [InlineKeyboardButton("🔗 Реферальная система", callback_data="referral")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            self.config.WELCOME_MESSAGE,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админ панель"""
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_USER_IDS:
            await update.message.reply_text("❌ У вас нет доступа к админ панели")
            return
        
        admin_menu = """
🏢 **Админ Панель PassiveNFT**

Доступные команды:

📊 `/alminserveraastat` - статистика подписок
👥 `/adminserveraapeople` - список участников  
🔗 `/adminserveraaref` - статистика рефералов

Выберите команду для просмотра статистики.
        """
        
        await update.message.reply_text(admin_menu, parse_mode='Markdown')
    
    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика подписок для админа"""
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_USER_IDS:
            return
        
        stats = self.db.get_subscription_stats()
        
        message = "📊 **Статистика подписок**\n\n"
        
        for sub_type, data in stats.items():
            sub_name = self.config.SUBSCRIPTIONS[sub_type]["name"]
            message += f"**{sub_name}:**\n"
            message += f"• Всего: {data['total']}\n"
            message += f"• Оплачено: {data['paid']}\n"
            message += f"• В ожидании: {data['pending']}\n\n"
        
        # Группировка по серверам (150 на сервер)
        message += "**Группировка по серверам (150 подписок на сервер):**\n\n"
        
        for sub_type, data in stats.items():
            sub_name = self.config.SUBSCRIPTIONS[sub_type]["name"]
            total = data['total']
            servers = (total + 149) // 150  # округление вверх
            
            message += f"**{sub_name}:**\n"
            for i in range(servers):
                server_start = i * 150 + 1
                server_end = min((i + 1) * 150, total)
                if server_start <= total:
                    message += f"• Сервер {i + 1}: {server_start}-{server_end} из {total}\n"
            message += "\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def admin_people(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список участников для админа"""
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_USER_IDS:
            return
        
        subscribers = self.db.get_subscribers()
        
        if not subscribers:
            message = "📋 **Список участников пуст**"
        else:
            message = "👥 **Список участников**\n\n"
            
            # Группировка по типу подписки
            grouped = {}
            for sub in subscribers:
                sub_type = sub["subscription"]
                if sub_type not in grouped:
                    grouped[sub_type] = []
                grouped[sub_type].append(sub)
            
            for sub_type, users in grouped.items():
                sub_name = self.config.SUBSCRIPTIONS[sub_type]["name"]
                message += f"**{sub_name}** ({len(users)} участников):\n"
                for user in users:
                    username = f"@{user['username']}" if user['username'] else user['name']
                    message += f"• {username}\n"
                message += "\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def admin_referrals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика рефералов для админа"""
        user_id = update.effective_user.id
        
        if user_id not in self.config.ADMIN_USER_IDS:
            return
        
        referral_stats = self.db.get_referral_stats()
        
        if not referral_stats:
            message = "🔗 **Реферальная статистика пуста**"
        else:
            message = "🔗 **Статистика рефералов**\n\n"
            
            for stat in referral_stats:
                if stat["total_referrals"] > 0:
                    username = f"@{stat['username']}" if stat['username'] else "Без имени"
                    commission = stat['commission'] or 0
                    
                    message += f"**{username}**\n"
                    message += f"• Код: `{stat['referral_code']}`\n"
                    message += f"• Всего рефералов: {stat['total_referrals']}\n"
                    message += f"• Оплатили: {stat['paid_referrals']}\n"
                    message += f"• Комиссия: {commission} TON\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        logger.info(f"Нажата кнопка: {data}")
        
        if data == "subscriptions":
            await self.show_subscriptions(query)
        elif data == "contact":
            await self.show_contact(query)
        elif data == "referral":
            await self.show_referral_system(query)
        elif data.startswith("sub_"):
            sub_type = data.replace("sub_", "")
            await self.show_subscription_details(query, sub_type)
        elif data == "back_to_main":
            await self.back_to_main(query)
        elif data == "back_to_subscriptions":
            await self.back_to_subscriptions(query)
        elif data == "back_to_referral":
            await self.back_to_referral(query)
        elif data == "pay":
            await self.show_payment(query)
        elif data == "get_referral_link":
            await self.get_referral_link(query)
        elif data == "referral_stats":
            await self.show_referral_stats(query)
        else:
            logger.warning(f"Неизвестная кнопка: {data}")
            await query.answer("❌ Неизвестная кнопка!")
    
    async def show_subscriptions(self, query):
        """Показать подписки"""
        keyboard = [
            [InlineKeyboardButton("👥 Подписка на 150 человек", callback_data="sub_150_people")],
            [InlineKeyboardButton("👥 Подписка на 100 человек", callback_data="sub_100_people")],
            [InlineKeyboardButton("👥 Подписка на 50 человек", callback_data="sub_50_people")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎯 **Выбери свою подписку:**\n\n💡 Нажми на интересующий тебя план",
            reply_markup=reply_markup
        )
    
    async def show_subscription_details(self, query, sub_type):
        """Показать детали подписки"""
        
        # Получаем сообщение для данного типа подписки
        message = subscription_messages.get(sub_type, "Подписка не найдена")
        
        keyboard = [
            [InlineKeyboardButton("💳 Оплатить", callback_data="pay")],
            [InlineKeyboardButton("⬅️ Назад к подпискам", callback_data="back_to_subscriptions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_payment(self, query):
        """Показать информацию об оплате"""
        payment_text = f"""
💳 **Оплата подписки**

Отправьте указанную сумму на следующий TON кошелек:

`{self.config.TON_WALLET_ADDRESS}`

После оплаты обратитесь к менеджеру для подтверждения.
        """
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад к подпискам", callback_data="back_to_subscriptions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            payment_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_contact(self, query):
        """Показать контактную информацию"""
        contact_text = f"📞 **Связь с менеджером**\n\n💬 Обратитесь к @{self.config.MANAGER_USERNAME} для вопросов по подписке"
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            contact_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_referral_system(self, query):
        """Показать реферальную систему"""
        referral_text = f"""🔗 **Реферальная система PassiveNFT**

💰 Приглашайте друзей и зарабатывайте 10% с каждой их покупки!

🎯 Как это работает:
• Поделитесь вашей реферальной ссылкой
• Друг регистрируется по ссылке
• Вы получаете 10% с каждой его покупки
• Бонус выплачивается автоматически

📞 **Поддержка:** @{self.config.MANAGER_USERNAME}"""
        
        keyboard = [
            [InlineKeyboardButton("🔗 Получить реферальную ссылку", callback_data="get_referral_link")],
            [InlineKeyboardButton("📊 Статистика рефералов", callback_data="referral_stats")],
            [InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            referral_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def get_referral_link(self, query):
        """Получить реферальную ссылку"""
        user_id = query.from_user.id
        referral_code = self.db.get_or_create_user(
            user_id,
            query.from_user.username or "",
            query.from_user.first_name or "",
            query.from_user.last_name or ""
        )
        
        bot_username = self.config.BOT_USERNAME
        referral_link = f"https://t.me/{bot_username}?start={referral_code}"
        
        message = f"""
🔗 **Ваша персональная реферальная ссылка:**

`{referral_link}`

Делитесь этой ссылкой с друзьями и получайте 10% с каждой их покупки!
        """
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад к рефералам", callback_data="back_to_referral")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def show_referral_stats(self, query):
        """Показать статистику рефералов"""
        user_id = query.from_user.id
        referral_stats = self.db.get_referral_stats()
        
        # Находим статистику текущего пользователя
        user_stats = next((stat for stat in referral_stats if stat.get('user_id') == user_id), None)
        
        if not user_stats:
            message = "📊 **Статистика рефералов**\n\nУ вас пока нет рефералов."
        else:
            message = f"""
📊 **Ваша статистика рефералов**

👥 Всего приглашено: {user_stats['total_referrals']}
✅ Оплатили: {user_stats['paid_referrals']}
💰 Заработано комиссии: {user_stats['commission'] or 0} TON
            """
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад к рефералам", callback_data="back_to_referral")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def create_referral(self, referrer_id: int, referred_id: int, referral_code: str):
        """Создать реферальную связь"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO referrals (referrer_id, referred_id, referral_code)
            VALUES (?, ?, ?)
        """, (referrer_id, referred_id, referral_code))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Создана реферальная связь: {referrer_id} -> {referred_id}")
    
    async def back_to_main(self, query):
        """Вернуться в главное меню"""
        keyboard = [
            [InlineKeyboardButton("💎 Подписки", callback_data="subscriptions")],
            [InlineKeyboardButton("📞 Связь с менеджером", callback_data="contact")],
            [InlineKeyboardButton("🔗 Реферальная система", callback_data="referral")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            self.config.WELCOME_MESSAGE,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def back_to_subscriptions(self, query):
        """Вернуться к подпискам"""
        await self.show_subscriptions(query)
    
    async def back_to_referral(self, query):
        """Вернуться к реферальной системе"""
        await self.show_referral_system(query)
    
    def run(self):
        """Запуск бота"""
        logger.info("🚀 Запуск PassiveNFT Bot на Render...")
        logger.info(f"🤖 Бот: @{self.config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...{self.config.TON_WALLET_ADDRESS[-10:]}")
        # Для Render используем polling
        self.application.run_polling(drop_pending_updates=True)

def main():
    """Главная функция"""
    bot = PassiveNFTBot()
    bot.run()

if __name__ == "__main__":
    main()
