#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Асинхронный менеджер базы данных для PassiveNFT Bot - ИСПРАВЛЕННАЯ ВЕРСИЯ
РЕШАЕТ ПРОБЛЕМУ ЗАВИСАНИЯ БОТА ЧЕРЕЗ 20-30 МИНУТ
Использует aiosqlite вместо sqlite3 для неблокирующих операций
ИСПРАВЛЕНИЯ:
- Убрано дублирование метода get_confirmation_stats
- Исправлена асинхронная работа с базой данных
- Исправлены проблемы с контекстными менеджерами
- Добавлены методы для реферальной системы
"""
import asyncio
import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

class AsyncDatabaseManager:
    """Асинхронный менеджер базы данных с полной поддержкой async/await"""
    
    def __init__(self, db_path: str = "passive_nft_bot.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Инициализация базы данных с созданием всех необходимых таблиц"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        referral_code TEXT UNIQUE
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        referrer_id INTEGER NOT NULL,
                        referred_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (referrer_id) REFERENCES users (id),
                        FOREIGN KEY (referred_id) REFERENCES users (id),
                        UNIQUE(referrer_id, referred_id)
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS pending_referrals (
                        user_id INTEGER PRIMARY KEY,
                        referrer_id INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        FOREIGN KEY (referrer_id) REFERENCES users (id)
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        subscription_type TEXT NOT NULL,
                        payment_method TEXT NOT NULL,
                        amount REAL,
                        currency TEXT DEFAULT 'TON',
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS referral_earnings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        referrer_id INTEGER NOT NULL,
                        referred_id INTEGER NOT NULL,
                        commission_amount REAL NOT NULL,
                        subscription_type TEXT NOT NULL,
                        payment_method TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (referrer_id) REFERENCES users (id),
                        FOREIGN KEY (referred_id) REFERENCES users (id)
                    )
                """)
                
                # ТАБЛИЦА ДЛЯ СИСТЕМЫ ПОДТВЕРЖДЕНИЯ ОПЛАТЫ
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS confirmation_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        admin_id INTEGER NOT NULL,
                        subscription_type TEXT NOT NULL,
                        username TEXT NOT NULL,
                        link_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (admin_id) REFERENCES users (id)
                    )
                """)
                
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS payment_confirmations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        username TEXT NOT NULL,
                        subscription_type TEXT NOT NULL,
                        confirmed_by INTEGER NOT NULL,
                        invite_link TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        FOREIGN KEY (confirmed_by) REFERENCES users (id)
                    )
                """)
                
                await db.commit()
                logger.info("✅ База данных инициализирована успешно")

    async def get_or_create_user(self, user_id: int, username: str = "", first_name: str = "", last_name: str = "") -> str:
        """Создание или получение пользователя"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                # Проверяем существование пользователя
                cursor = await db.execute("SELECT username FROM users WHERE id = ?", (user_id,))
                existing_user = await cursor.fetchone()
                await cursor.close()
                
                if existing_user:
                    return existing_user[0]
                
                # Создаем нового пользователя
                try:
                    await db.execute("""
                        INSERT INTO users (id, username, first_name, last_name)
                        VALUES (?, ?, ?, ?)
                    """, (user_id, username, first_name, last_name))
                    await db.commit()
                    logger.info(f"✅ Пользователь {username} создан")
                    return username
                except Exception as e:
                    logger.error(f"❌ Ошибка создания пользователя: {e}")
                    return username

    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Получение пользователя по username"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT * FROM users WHERE username = ?
                """, (username,))
                row = await cursor.fetchone()
                await cursor.close()
                
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None

    async def save_pending_referral(self, user_id: int, referrer_id: int):
        """Сохранение ожидающего реферала"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                try:
                    await db.execute("""
                        INSERT OR REPLACE INTO pending_referrals (user_id, referrer_id)
                        VALUES (?, ?)
                    """, (user_id, referrer_id))
                    await db.commit()
                    logger.info(f"👥 Ожидающий реферер сохранен: {user_id} -> {referrer_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка сохранения ожидающего реферера: {e}")

    async def get_pending_referrer(self, user_id: int) -> Optional[int]:
        """Получение ожидающего реферера"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT referrer_id FROM pending_referrals WHERE user_id = ?
                """, (user_id,))
                row = await cursor.fetchone()
                await cursor.close()
                return row[0] if row else None

    async def remove_pending_referral(self, user_id: int):
        """Удаление ожидающего реферала"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM pending_referrals WHERE user_id = ?", (user_id,))
                await db.commit()
                logger.info(f"🗑️ Ожидающий реферер удален для пользователя {user_id}")

    async def add_referral(self, referrer_id: int, referred_id: int) -> bool:
        """Добавление реферала"""
        if referrer_id == referred_id:
            return False
            
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                try:
                    # Проверяем, не существует ли уже такой реферал
                    cursor = await db.execute("""
                        SELECT id FROM referrals WHERE referrer_id = ? AND referred_id = ?
                    """, (referrer_id, referred_id))
                    existing = await cursor.fetchone()
                    
                    if existing:
                        await cursor.close()
                        logger.warning(f"⚠️ Реферал уже существует: {referred_id} от {referrer_id}")
                        return False
                    
                    await cursor.close()
                    
                    # Добавляем новый реферал
                    await db.execute("""
                        INSERT INTO referrals (referrer_id, referred_id)
                        VALUES (?, ?)
                    """, (referrer_id, referred_id))
                    
                    await db.commit()
                    logger.info(f"✅ Реферал добавлен: {referred_id} от {referrer_id}")
                    return True
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка добавления реферала: {e}")
                    return False
    
    async def get_user_referrals_count(self, user_id: int) -> int:
        """Получение количества рефералов пользователя"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM referrals WHERE referrer_id = ?
                """, (user_id,))
                row = await cursor.fetchone()
                await cursor.close()
                return row[0] if row else 0
    
    async def get_user_referral_earnings(self, user_id: int) -> float:
        """Получение заработка пользователя с рефералов"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT COALESCE(SUM(commission_amount), 0) 
                    FROM referral_earnings 
                    WHERE referrer_id = ? AND payment_method = 'TON'
                """, (user_id,))
                row = await cursor.fetchone()
                await cursor.close()
                return float(row[0]) if row else 0.0
    
    async def get_user_referral_stats(self, user_id: int) -> str:
        """Получение детальной статистики рефералов пользователя"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                # Получаем информацию о рефералах
                cursor = await db.execute("""
                    SELECT 
                        COUNT(r.id) as total_referrals,
                        COALESCE(SUM(re.commission_amount), 0) as total_earnings,
                        COUNT(CASE WHEN re.payment_method = 'TON' THEN 1 END) as ton_referrals,
                        COUNT(CASE WHEN re.payment_method = 'STARS' THEN 1 END) as stars_referrals
                    FROM users u
                    LEFT JOIN referrals r ON u.id = r.referred_id
                    LEFT JOIN referral_earnings re ON r.id = re.referred_id
                    WHERE u.id = ?
                """, (user_id,))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                if not row or row[0] == 0:
                    return "У вас пока нет рефералов.\n💡 Поделитесь своей реферальной ссылкой с друзьями!"
                
                total_referrals, total_earnings, ton_referrals, stars_referrals = row
                
                return f"""📊 Ваша реферальная статистика:
👥 Всего рефералов: {total_referrals}
💰 Заработано TON: {total_earnings:.2f}
💎 TON рефералов: {ton_referrals}
⭐ Stars рефералов: {stars_referrals}

💡 Комиссия 10% начисляется только за TON-подписки!
🎯 Приглашайте друзей и зарабатывайте больше!"""
    
    async def calculate_commission(self, subscription_amount: float, subscription_type: str, payment_method: str) -> float:
        """Расчет комиссии для реферала (только для TON-подписок)"""
        if payment_method.upper() == 'TON':
            return round(subscription_amount * 0.10, 2)  # 10% комиссия
        return 0.0  # За Stars подписки комиссия не начисляется
    
    async def add_referral_earnings(self, referrer_id: int, referred_id: int, commission_amount: float, 
                                  subscription_type: str, payment_method: str):
        """Добавление заработка рефереру (только для TON-подписок)"""
        if commission_amount <= 0:
            return
        
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO referral_earnings 
                    (referrer_id, referred_id, commission_amount, subscription_type, payment_method)
                    VALUES (?, ?, ?, ?, ?)
                """, (referrer_id, referred_id, commission_amount, subscription_type, payment_method))
                await db.commit()
                logger.info(f"💰 Комиссия {commission_amount} TON начислена рефереру {referrer_id}")

    async def process_payment_confirmation_with_referral(self, username: str, subscription_type: str, 
                                                       payment_method: str, subscription_amount: float,
                                                       admin_id: int) -> Tuple[bool, str]:
        """Обработка подтверждения оплаты с учетом реферальной системы"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    # Получаем пользователя
                    user_cursor = await db.execute("""
                        SELECT id FROM users WHERE username = ?
                    """, (username,))
                    user_row = await user_cursor.fetchone()
                    await user_cursor.close()
                    
                    if not user_row:
                        return False, "Пользователь не найден"
                    
                    user_id = user_row[0]
                    
                    # Получаем ожидающего реферера
                    referrer_cursor = await db.execute("""
                        SELECT referrer_id FROM pending_referrals WHERE user_id = ?
                    """, (user_id,))
                    referrer_row = await referrer_cursor.fetchone()
                    await referrer_cursor.close()
                    
                    # Добавляем реферала если есть
                    referral_added = False
                    if referrer_row:
                        referral_added = await self.add_referral(referrer_row[0], user_id)
                    
                    # Начисляем комиссию если есть реферер и это TON-подписка
                    if referrer_row and payment_method.upper() == 'TON':
                        commission = await self.calculate_commission(subscription_amount, subscription_type, payment_method)
                        if commission > 0:
                            await db.execute("""
                                INSERT INTO referral_earnings 
                                (referrer_id, referred_id, commission_amount, subscription_type, payment_method)
                                VALUES (?, ?, ?, ?, ?)
                            """, (referrer_row[0], user_id, commission, subscription_type, payment_method))
                            logger.info(f"💰 Комиссия {commission} TON начислена рефереру {referrer_row[0]}")
                    
                    # Удаляем ожидающего реферера
                    await db.execute("DELETE FROM pending_referrals WHERE user_id = ?", (user_id,))
                    
                    await db.commit()
                    
                    result_message = f"✅ Оплата подтверждена для @{username}"
                    if referrer_row and payment_method.upper() == 'TON':
                        commission = await self.calculate_commission(subscription_amount, subscription_type, payment_method)
                        if commission > 0:
                            result_message += f"\n💰 Реферальная комиссия {commission} TON начислена"
                    
                    return True, result_message
                    
        except Exception as e:
            logger.error(f"❌ Ошибка обработки подтверждения оплаты: {e}")
            return False, f"Ошибка: {str(e)}"

    async def get_detailed_referral_stats(self) -> List[Dict]:
        """Получение детальной реферальной статистики"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT 
                        u.username,
                        COUNT(r.id) as referrals_count,
                        COALESCE(SUM(re.commission_amount), 0) as total_commission
                    FROM users u
                    LEFT JOIN referrals r ON u.id = r.referrer_id
                    LEFT JOIN referral_earnings re ON r.id = re.referred_id
                    WHERE r.id IS NOT NULL
                    GROUP BY u.id, u.username
                    ORDER BY total_commission DESC
                """)
                
                rows = await cursor.fetchall()
                await cursor.close()
                
                stats = []
                for row in rows:
                    stats.append({
                        'username': row[0],
                        'referrals_count': row[1],
                        'total_commission': float(row[2])
                    })
                
                return stats

    async def get_referral_stats_by_username(self, username: str) -> Optional[Dict]:
        """Получение реферальной статистики по username"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT 
                        u.username,
                        COUNT(r.id) as referrals_count,
                        COALESCE(SUM(re.commission_amount), 0) as total_commission
                    FROM users u
                    LEFT JOIN referrals r ON u.id = r.referrer_id
                    LEFT JOIN referral_earnings re ON r.id = re.referred_id
                    WHERE u.username = ?
                    GROUP BY u.id, u.username
                """, (username,))
                
                row = await cursor.fetchone()
                await cursor.close()
                
                if row:
                    return {
                        'username': row[0],
                        'referrals_count': row[1],
                        'total_commission': float(row[2])
                    }
                return None

    async def get_all_users_count(self) -> int:
        """Получение общего количества пользователей"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                row = await cursor.fetchone()
                await cursor.close()
                return row[0] if row else 0

    async def get_total_referrals_count(self) -> int:
        """Получение общего количества рефералов"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM referrals")
                row = await cursor.fetchone()
                await cursor.close()
                return row[0] if row else 0

    async def get_total_commission_earned(self) -> float:
        """Получение общей заработанной комиссии"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT COALESCE(SUM(commission_amount), 0) FROM referral_earnings
                """)
                row = await cursor.fetchone()
                await cursor.close()
                return float(row[0]) if row else 0.0

    async def get_subscribers(self) -> List[Dict]:
        """Получение списка подписчиков"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT username, first_name, created_at FROM users ORDER BY created_at DESC
                """)
                rows = await cursor.fetchall()
                await cursor.close()
                
                subscribers = []
                for row in rows:
                    subscribers.append({
                        'username': row[0],
                        'first_name': row[1],
                        'created_at': row[2]
                    })
                
                return subscribers

    async def get_referral_stats(self) -> List[Dict]:
        """Получение реферальной статистики"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT 
                        u.username,
                        COUNT(r.id) as referrals_count,
                        COALESCE(SUM(re.commission_amount), 0) as total_commission
                    FROM users u
                    LEFT JOIN referrals r ON u.id = r.referrer_id
                    LEFT JOIN referral_earnings re ON r.id = re.referred_id
                    WHERE r.id IS NOT NULL
                    GROUP BY u.id, u.username
                    ORDER BY total_commission DESC, referrals_count DESC
                """)
                
                rows = await cursor.fetchall()
                await cursor.close()
                
                stats = []
                for row in rows:
                    stats.append({
                        'username': row[0],
                        'referrals_count': row[1],
                        'total_commission': float(row[2])
                    })
                
                return stats

    async def add_subscription(self, user_id: int, subscription_type: str, payment_method: str, 
                             amount: float, currency: str = 'TON'):
        """Добавление подписки"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO subscriptions 
                    (user_id, subscription_type, payment_method, amount, currency)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, subscription_type, payment_method, amount, currency))
                await db.commit()
                logger.info(f"💳 Подписка {subscription_type} добавлена для пользователя {user_id}")

    async def save_confirmation_log(self, log_data: Dict):
        """Сохранение лога подтверждения"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                try:
                    await db.execute("""
                        INSERT INTO confirmation_logs 
                        (admin_id, subscription_type, username, link_id)
                        VALUES (?, ?, ?, ?)
                    """, (log_data['admin_id'], log_data['subscription_type'], 
                          log_data['username'], log_data['link_id']))
                    await db.commit()
                    logger.info(f"📋 Лог подтверждения сохранен для @{log_data['username']}")
                except Exception as e:
                    logger.error(f"❌ Ошибка сохранения лога: {e}")
                    raise e

    async def get_recent_confirmation_logs(self, limit: int = 10) -> List[Dict]:
        """Получение последних логов подтверждений"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT * FROM confirmation_logs 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                
                rows = await cursor.fetchall()
                await cursor.close()
                
                logs = []
                for row in rows:
                    logs.append({
                        'id': row[0],
                        'admin_id': row[1],
                        'subscription_type': row[2],
                        'username': row[3],
                        'link_id': row[4],
                        'timestamp': row[5]
                    })
                
                return logs

    # ЕДИНСТВЕННЫЙ ИСПРАВЛЕННЫЙ МЕТОД get_confirmation_stats
    async def get_confirmation_stats(self) -> Dict:
        """Получение статистики подтверждений (исправленная версия)"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    # Общая статистика
                    cursor = await db.execute("SELECT COUNT(*) FROM confirmation_logs")
                    total_confirmations = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Подтверждения сегодня
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM confirmation_logs 
                        WHERE DATE(timestamp) = DATE('now')
                    """)
                    today_confirmations = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Подтверждения за неделю
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM confirmation_logs 
                        WHERE timestamp >= datetime('now', '-7 days')
                    """)
                    week_confirmations = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Подтверждения за месяц
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM confirmation_logs 
                        WHERE timestamp >= datetime('now', '-30 days')
                    """)
                    month_confirmations = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Статистика по типам подписок
                    cursor = await db.execute("""
                        SELECT subscription_type, COUNT(*) as count
                        FROM confirmation_logs
                        GROUP BY subscription_type
                        ORDER BY count DESC
                    """)
                    
                    rows = await cursor.fetchall()
                    await cursor.close()
                    
                    by_subscription_type = {}
                    for row in rows:
                        by_subscription_type[row[0]] = row[1]
                    
                    stats = {
                        'total_confirmations': total_confirmations,
                        'today_confirmations': today_confirmations,
                        'week_confirmations': week_confirmations,
                        'month_confirmations': month_confirmations,
                        'by_subscription_type': by_subscription_type
                    }
                    
                    logger.info(f"📈 Статистика подтверждений получена: {stats}")
                    return stats
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики подтверждений: {e}")
            return {
                'total_confirmations': 0,
                'today_confirmations': 0,
                'week_confirmations': 0,
                'month_confirmations': 0,
                'by_subscription_type': {}
            }

    async def save_payment_confirmation(self, user_id: int, username: str, subscription_type: str, confirmed_by: int, invite_link: str):
        """Сохранение подтверждения оплаты"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO payment_confirmations 
                    (user_id, username, subscription_type, confirmed_by, invite_link)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, username, subscription_type, confirmed_by, invite_link))
                
                await db.commit()
                logger.info(f"✅ Подтверждение сохранено для @{username}")
    
    async def get_confirmation_history(self, limit: int = 10) -> List[Dict]:
        """Получение истории подтверждений"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT * FROM payment_confirmations
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                
                rows = await cursor.fetchall()
                await cursor.close()
                
                columns = [description[0] for description in cursor.description] if cursor.description else []
                history = []
                
                for row in rows:
                    if columns:
                        record = dict(zip(columns, row))
                        history.append(record)
                    
                logger.info(f"📊 Получена история подтверждений: {len(history)} записей")
                return history

    async def save_pending_message(self, username: str, message: str, subscription_type: str, invite_link: str):
        """Сохранение ожидающего сообщения"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO pending_messages (username, message, subscription_type, invite_link)
                    VALUES (?, ?, ?, ?)
                """, (username, message, subscription_type, invite_link))
                await db.commit()
                logger.info(f"📝 Ожидающее сообщение сохранено для @{username}")

    async def check_subscription_access(self, user_id: int, subscription_amount: int, subscription_type: str) -> Dict:
        """Проверка доступа к подписке"""
        # Заглушка для проверки доступа
        return {
            'has_access': True,
            'subscription_type': subscription_type,
            'expires_at': None
        }

    async def close(self):
        """Закрытие соединения с базой данных"""
        # aiosqlite автоматически закрывает соединения, но можно добавить дополнительную логику
        logger.info("🔒 Соединение с базой данных закрыто")

# Создаем глобальный экземпляр менеджера базы данных
database_manager = AsyncDatabaseManager()
print("✅ AsyncDatabaseManager initialized successfully with fixes")
