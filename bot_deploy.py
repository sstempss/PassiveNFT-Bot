"""
Финальная версия бота с очисткой состояния для решения конфликтов
"""
import logging
import asyncio
import sqlite3
from typing import Dict, Any
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config_deploy_new import *

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                referral_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER,
                subscription_type TEXT,
                purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER,
                referred_id INTEGER,
                commission_amount REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    
    def get_user(self, user_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    
    def create_user(self, user_id: int, username: str, first_name: str, referral_id: int = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, referral_id)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, referral_id))
        conn.commit()
        conn.close()
    
    def get_user_referrals(self, user_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as count, COALESCE(SUM(commission_amount), 0) as total_commission
            FROM referrals WHERE referrer_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result

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
            'CONTACT_MESSAGE': CONTACT_MESSAGE,
            'REFERRAL_MESSAGE': REFERRAL_MESSAGE,
            'DATABASE_PATH': DATABASE_PATH
        })()
        self.db = DatabaseManager(self.config.DATABASE_PATH)
        self.application = Application.builder().token(self.config.BOT_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

    async def clear_webhook_on_startup(self):
        """Очистка webhook при запуске для избежания конфликтов"""
        try:
            logger.info("🧹 Очистка старых webhook'ов...")
            await self.application.bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook очищен успешно")
        except Exception as e:
            logger.warning(f"⚠️ Предупреждение при очистке webhook: {e}")

    def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        args = context.args
        
        referral_id = None
        if args:
            try:
                referral_id = int(args[0])
            except (ValueError, IndexError):
                pass
        
        self.db.create_user(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            referral_id=referral_id
        )
        
        keyboard = [
            [InlineKeyboardButton("💎 Подписки", callback_data="show_subscriptions")],
            [InlineKeyboardButton("📞 Связь с менеджером", callback_data="show_contact")],
            [InlineKeyboardButton("🔗 Реферальная система", callback_data="show_referrals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            self.config.WELCOME_MESSAGE,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        query.answer()
        
        if query.data == "show_subscriptions":
            self.show_subscriptions(query)
        elif query.data == "show_contact":
            self.show_contact(query)
        elif query.data == "show_referrals":
            self.show_referrals(query)
        elif query.data.startswith("subscription_"):
            subscription_type = query.data.replace("subscription_", "")
            self.show_subscription_details(query, subscription_type)
        elif query.data == "buy_subscription":
            self.show_buy_subscription(query)
    
    def show_subscriptions(self, query):
        message = "💎 **Доступные подписки PassiveNFT**\n\n"
        
        for sub_type, sub_data in self.config.SUBSCRIPTIONS.items():
            message += f"**{sub_data['name']}** - {sub_data['price']} TON/месяц\n"
            message += f"• NFT в день: {sub_data.get('nft_per_day', 'N/A')}\n"
            message += f"• ROI: {sub_data.get('roi_range', 'N/A')}\n\n"
        
        keyboard = []
        for sub_type in self.config.SUBSCRIPTIONS.keys():
            keyboard.append([InlineKeyboardButton(
                f"Подробнее: {self.config.SUBSCRIPTIONS[sub_type]['name']}",
                callback_data=f"subscription_{sub_type}"
            )])
        
        keyboard.append([InlineKeyboardButton("💳 Купить подписку", callback_data="buy_subscription")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def show_subscription_details(self, query, subscription_type):
        if subscription_type not in self.config.SUBSCRIPTIONS:
            query.answer("Неизвестный тип подписки")
            return
        
        sub_data = self.config.SUBSCRIPTIONS[subscription_type]
        
        message = f"💎 **{sub_data['name']}**\n\n"
        message += f"💰 **Цена:** {sub_data['price']} TON/месяц\n\n"
        message += f"📊 **Статистика:**\n"
        message += f"• NFT в день: {sub_data.get('nft_per_day', 'N/A')}\n"
        message += f"• NFT в месяц: {sub_data.get('nft_per_month', 'N/A')}\n"
        message += f"• Подарки в день: {sub_data.get('gifts_per_day', 'N/A')}\n"
        message += f"• Подарки в месяц: {sub_data.get('gifts_per_month', 'N/A')}\n"
        message += f"• Процент выигрышей NFT: {sub_data.get('nft_win_percentage', 'N/A')}%\n"
        message += f"• Процент выигрышей подарков: {sub_data.get('gifts_win_percentage', 'N/A')}%\n\n"
        
        if 'min_refund' in sub_data:
            message += f"💸 **Минимальный возврат:** {sub_data['min_refund']}\n\n"
        
        if 'refund' in sub_data:
            message += f"💸 **Возврат:** {sub_data['refund']}\n\n"
        
        message += f"🎯 **Потенциальная прибыль:** {sub_data.get('roi_range', 'N/A')}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("💳 Купить подписку", callback_data="buy_subscription")],
            [InlineKeyboardButton("🔙 К списку подписок", callback_data="show_subscriptions")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def show_contact(self, query):
        message = self.config.CONTACT_MESSAGE
        keyboard = [
            [InlineKeyboardButton("💬 Написать менеджеру", url=f"https://t.me/{self.config.MANAGER_USERNAME}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="show_subscriptions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def show_referrals(self, query):
        message = self.config.REFERRAL_MESSAGE
        
        user = query.from_user
        bot_username = self.config.BOT_USERNAME
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        
        referral_stats = self.db.get_user_referrals(user.id)
        referrals_count = referral_stats[0] if referral_stats else 0
        total_commission = referral_stats[1] if referral_stats else 0
        
        message += f"\n\n🔗 **Ваша реферальная ссылка:**\n`{referral_link}`\n\n"
        message += f"📊 **Ваша статистика:**\n"
        message += f"• Приглашено друзей: {referrals_count}\n"
        message += f"• Общая комиссия: {total_commission:.2f} TON"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="show_subscriptions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def show_buy_subscription(self, query):
        message = f"""💳 **Покупка подписки PassiveNFT**

💰 Для оплаты используйте следующий адрес TON кошелька:

`{self.config.TON_WALLET_ADDRESS}`

📱 **Как оплатить:**
1. Скопируйте адрес кошелька
2. Откройте TON кошелек
3. Отправьте нужную сумму
4. Отправьте скриншот оплаты менеджеру: @{self.config.MANAGER_USERNAME}

📞 **Поддержка:** @{self.config.MANAGER_USERNAME}

⚡ После оплаты вы получите доступ к выбранной подписке!"""
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="show_subscriptions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def run(self):
        """Запуск бота с очисткой состояния"""
        logger.info("🚀 Запуск PassiveNFT Bot на Render...")
        logger.info(f"🤖 Бот: @{self.config.BOT_USERNAME}")
        logger.info(f"💰 Кошелек: {self.config.TON_WALLET_ADDRESS[:10]}...{self.config.TON_WALLET_ADDRESS[-10:]}")
        
        # Очистка webhook перед запуском
        await self.clear_webhook_on_startup()
        
        # Запуск polling
        await self.application.initialize()
        await self.application.start()
        
        try:
            await self.application.updater.start_polling()
            logger.info("✅ Бот запущен и ожидает команды...")
            await self.application.idle()
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
            raise
        finally:
            await self.application.stop()
            await self.application.shutdown()

async def main():
    """Главная асинхронная функция"""
    bot = PassiveNFTBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
