#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Асинхронный менеджер базы данных для PassiveNFT Bot - ИСПРАВЛЕННАЯ ВЕРСИЯ С РЕФЕРАЛЬНОЙ СИСТЕМОЙ
РЕШАЕТ ПРОБЛЕМУ ЗАВИСАНИЯ БОТА ЧЕРЕЗ 20-30 МИНУТ
Использует aiosqlite вместо sqlite3 для неблокирующих операций
ИСПРАВЛЕНИЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ:
- Добавлены методы для обработки подтверждений оплаты с реферальной системой
- Автоматический расчет 10% комиссии для TON-подписок
- Улучшенная статистика рефералов с детальной информацией
- Методы для админского просмотра реферальной статистики
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
                
                # НОВАЯ ТАБЛИЦА ДЛЯ СИСТЕМЫ ПОДТВЕРЖДЕНИЯ ОПЛАТЫ
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS confirmation_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        admin_id INTEGER NOT NULL,
                        subscription_type TEXT NOT NULL,
                        username TEXT NOT NULL,
                        link_id TEXT NOT NULL UNIQUE,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # ТАБЛИЦА ДЛЯ ОЧЕРЕДИ ОТЛОЖЕННЫХ СООБЩЕНИЙ
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS pending_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL,
                        message TEXT NOT NULL,
                        subscription_type TEXT NOT NULL,
                        invite_link TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # ТАБЛИЦА ДЛЯ ПОДТВЕРЖДЕНИЙ ОПЛАТЫ (КОТОРАЯ ИСПОЛЬЗУЕТСЯ В БОТЕ)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS payment_confirmations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        username TEXT NOT NULL,
                        subscription_type TEXT NOT NULL,
                        confirmed_by INTEGER NOT NULL,
                        invite_link TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                await db.commit()
                logger.info("✅ Асинхронная база данных инициализирована с системой подтверждения оплаты")
    
    async def get_or_create_user(self, user_id: int, username: str = "", first_name: str = "", last_name: str = "") -> str:
        """Получение или создание пользователя с реферальным кодом"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                # Проверяем, существует ли пользователь
                cursor = await db.execute("SELECT referral_code FROM users WHERE id = ?", (user_id,))
                row = await cursor.fetchone()
                
                if row:
                    await cursor.close()
                    return row[0]
                
                # Создаем нового пользователя
                referral_code = f"ref_{user_id}"
                
                await db.execute("""
                    INSERT OR IGNORE INTO users (id, username, first_name, last_name, referral_code)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, referral_code))
                
                await db.commit()
                logger.info(f"✅ Пользователь {user_id} создан в базе данных")
                return referral_code
    
    async def save_pending_referral(self, user_id: int, referrer_id: int):
        """Сохранение информации о временном реферале"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO pending_referrals (user_id, referrer_id)
                    VALUES (?, ?)
                """, (user_id, referrer_id))
                await db.commit()
                logger.info(f"⏳ Ожидающий реферер сохранен: пользователь {user_id} от {referrer_id}")
    
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
        """Удаление записи об ожидающем реферале"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM pending_referrals WHERE user_id = ?", (user_id,))
                await db.commit()
    
    async def add_referral(self, referrer_id: int, referred_id: int) -> bool:
        """Добавление реферала с предотвращением дублирования"""
        if referrer_id == referred_id:
            return False
        
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                try:
                    # Проверяем, не существует ли уже такая связь
                    cursor = await db.execute("""
                        SELECT id FROM referrals WHERE referrer_id = ? AND referred_id = ?
                    """, (referrer_id, referred_id))
                    
                    if await cursor.fetchone():
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
    
    # ========== НОВЫЕ МЕТОДЫ ДЛЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ В ПОДТВЕРЖДЕНИИ ОПЛАТЫ ==========
    
    async def process_payment_confirmation_with_referral(self, username: str, subscription_type: str, 
                                                       subscription_amount: float, payment_method: str,
                                                       admin_id: int, referrer_id: Optional[int] = None) -> Dict:
        """Обработка подтверждения оплаты с автоматическим расчетом реферальной комиссии"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    # Сначала получим или создадим пользователя
                    cursor = await db.execute("SELECT id FROM users WHERE username = ?", (username,))
                    row = await cursor.fetchone()
                    
                    user_id = None
                    if row:
                        user_id = row[0]
                        await cursor.close()
                    else:
                        # Создаем нового пользователя
                        await cursor.close()
                        await db.execute("""
                            INSERT OR IGNORE INTO users (id, username, referral_code)
                            VALUES (?, ?, ?)
                        """, (hash(username) % 1000000000, username, f"ref_{hash(username) % 1000000000}"))
                        user_id = hash(username) % 1000000000
                    
                    # Добавляем подписку
                    await db.execute("""
                        INSERT INTO subscriptions 
                        (user_id, subscription_type, payment_method, amount, currency, status)
                        VALUES (?, ?, ?, ?, ?, 'confirmed')
                    """, (user_id, subscription_type, payment_method, subscription_amount, payment_method))
                    
                    # Добавляем запись в payment_confirmations
                    await db.execute("""
                        INSERT INTO payment_confirmations 
                        (user_id, username, subscription_type, confirmed_by, invite_link)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, username, subscription_type, admin_id, "auto_generated"))
                    
                    # ОБРАБОТКА РЕФЕРАЛЬНОЙ СИСТЕМЫ
                    result = {
                        'user_id': user_id,
                        'referrer_found': False,
                        'commission_calculated': 0.0,
                        'referrer_id': None
                    }
                    
                    if payment_method.upper() == 'TON' and referrer_id:
                        # Проверяем, что реферер существует
                        cursor = await db.execute("SELECT id FROM users WHERE id = ?", (referrer_id,))
                        referrer_exists = await cursor.fetchone()
                        await cursor.close()
                        
                        if referrer_exists:
                            # Добавляем реферала если его еще нет
                            await self.add_referral(referrer_id, user_id)
                            
                            # Рассчитываем и начисляем комиссию
                            commission = await self.calculate_commission(
                                subscription_amount, subscription_type, payment_method
                            )
                            
                            await self.add_referral_earnings(
                                referrer_id, user_id, commission, subscription_type, payment_method
                            )
                            
                            # Удаляем ожидающего реферера если он есть
                            await self.remove_pending_referral(user_id)
                            
                            result.update({
                                'referrer_found': True,
                                'commission_calculated': commission,
                                'referrer_id': referrer_id
                            })
                            
                            logger.info(f"💰 Реферальная комиссия {commission} TON начислена рефереру {referrer_id}")
                    
                    await db.commit()
                    logger.info(f"✅ Подтверждение оплаты обработано для @{username}")
                    return result
                    
        except Exception as e:
            logger.error(f"❌ Ошибка обработки подтверждения оплаты: {e}")
            raise e
    
    async def get_detailed_referral_stats(self) -> List[Dict]:
        """Получение детальной статистики рефералов для админов"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        SELECT 
                            u.username as referrer_username,
                            u.first_name as referrer_name,
                            COUNT(r.id) as total_referrals,
                            COALESCE(SUM(re.commission_amount), 0) as total_earnings,
                            COUNT(CASE WHEN re.payment_method = 'TON' THEN 1 END) as ton_referrals,
                            COUNT(CASE WHEN re.payment_method = 'STARS' THEN 1 END) as stars_referrals,
                            COALESCE(SUM(CASE WHEN re.payment_method = 'TON' THEN re.commission_amount ELSE 0 END), 0) as ton_earnings
                        FROM users u
                        LEFT JOIN referrals r ON u.id = r.referrer_id
                        LEFT JOIN referral_earnings re ON r.referred_id = re.referred_id
                        GROUP BY u.id
                        HAVING COUNT(r.id) > 0
                        ORDER BY total_earnings DESC, total_referrals DESC
                    """)
                    
                    rows = await cursor.fetchall()
                    await cursor.close()
                    
                    stats = []
                    for row in rows:
                        stats.append({
                            'referrer_username': row[0] or 'Без username',
                            'referrer_name': row[1] or 'Без имени',
                            'total_referrals': row[2],
                            'total_earnings': float(row[3]),
                            'ton_referrals': row[4],
                            'stars_referrals': row[5],
                            'ton_earnings': float(row[6])
                        })
                    
                    return stats
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения детальной реферальной статистики: {e}")
            return []
    
    async def get_referral_stats_by_username(self, username: str) -> Optional[Dict]:
        """Получение реферальной статистики по конкретному username"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        SELECT 
                            u.username,
                            u.first_name,
                            u.last_name,
                            COUNT(r.id) as total_referrals,
                            COALESCE(SUM(re.commission_amount), 0) as total_earnings,
                            COUNT(CASE WHEN re.payment_method = 'TON' THEN 1 END) as ton_referrals,
                            COUNT(CASE WHEN re.payment_method = 'STARS' THEN 1 END) as stars_referrals,
                            COALESCE(SUM(CASE WHEN re.payment_method = 'TON' THEN re.commission_amount ELSE 0 END), 0) as ton_earnings
                        FROM users u
                        LEFT JOIN referrals r ON u.id = r.referrer_id
                        LEFT JOIN referral_earnings re ON r.referred_id = re.referred_id
                        WHERE u.username = ?
                        GROUP BY u.id
                    """, (username,))
                    
                    row = await cursor.fetchone()
                    await cursor.close()
                    
                    if row:
                        return {
                            'username': row[0] or 'Без username',
                            'first_name': row[1] or 'Без имени',
                            'last_name': row[2] or '',
                            'total_referrals': row[3],
                            'total_earnings': float(row[4]),
                            'ton_referrals': row[5],
                            'stars_referrals': row[6],
                            'ton_earnings': float(row[7])
                        }
                    
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения реферальной статистики для @{username}: {e}")
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
        """Получение общего заработанного TON по комиссиям"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT COALESCE(SUM(commission_amount), 0) 
                    FROM referral_earnings 
                    WHERE payment_method = 'TON'
                """)
                row = await cursor.fetchone()
                await cursor.close()
                return float(row[0]) if row else 0.0
    
    async def get_subscribers(self) -> List[Dict]:
        """Получение списка подписчиков"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT 
                        u.id,
                        u.username,
                        u.first_name,
                        u.last_name,
                        s.subscription_type,
                        s.status
                    FROM users u
                    LEFT JOIN subscriptions s ON u.id = s.user_id
                    ORDER BY u.created_at DESC
                    LIMIT 20
                """)
                rows = await cursor.fetchall()
                await cursor.close()
                
                subscribers = []
                for row in rows:
                    subscribers.append({
                        'id': row[0],
                        'username': row[1] or 'Нет',
                        'name': f"{row[2] or ''} {row[3] or ''}".strip() or 'Нет имени',
                        'subscription': row[4] or 'Не подписан',
                        'status': row[5] or 'pending'
                    })
                
                return subscribers
    
    async def get_referral_stats(self) -> List[Dict]:
        """Получение статистики рефералов по реферерам"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT 
                        u.username,
                        u.first_name,
                        COUNT(r.id) as total_referrals,
                        COALESCE(SUM(re.commission_amount), 0) as commission
                    FROM users u
                    LEFT JOIN referrals r ON u.id = r.referrer_id
                    LEFT JOIN referral_earnings re ON r.referred_id = re.referred_id
                    GROUP BY u.id
                    HAVING COUNT(r.id) > 0
                    ORDER BY total_referrals DESC
                    LIMIT 10
                """)
                rows = await cursor.fetchall()
                await cursor.close()
                
                stats = []
                for row in rows:
                    stats.append({
                        'username': row[0] or f"ID:{row[1]}",
                        'total_referrals': row[2],
                        'commission': float(row[3])
                    })
                
                return stats
    
    async def add_subscription(self, user_id: int, subscription_type: str, payment_method: str, 
                             amount: float, currency: str = 'TON') -> bool:
        """Добавление подписки с автоматическим начислением реферальной комиссии"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    # Добавляем подписку
                    cursor = await db.execute("""
                        INSERT INTO subscriptions 
                        (user_id, subscription_type, payment_method, amount, currency, status)
                        VALUES (?, ?, ?, ?, ?, 'confirmed')
                    """, (user_id, subscription_type, payment_method, amount, currency))
                    
                    # Проверяем, есть ли ожидающий реферер
                    pending_referrer = await self.get_pending_referrer(user_id)
                    
                    if pending_referrer and payment_method.upper() == 'TON':
                        # Начисляем комиссию только за TON-подписки
                        commission = await self.calculate_commission(amount, subscription_type, payment_method)
                        
                        # Добавляем запись о заработке
                        await self.add_referral_earnings(
                            pending_referrer, user_id, commission, subscription_type, payment_method
                        )
                        
                        # Удаляем ожидающего реферера
                        await self.remove_pending_referral(user_id)
                        
                        logger.info(f"💰 Комиссия {commission} TON начислена рефереру {pending_referrer}")
                    
                    await db.commit()
                    logger.info(f"✅ Подписка добавлена для пользователя {user_id}")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Ошибка добавления подписки: {e}")
            return False
    
    # ===== МЕТОДЫ ДЛЯ СИСТЕМЫ ПОДТВЕРЖДЕНИЯ ОПЛАТЫ =====
    
    async def save_confirmation_log(self, log_data: Dict):
        """Сохранение лога подтверждения оплаты"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("""
                        INSERT INTO confirmation_logs (admin_id, subscription_type, username, link_id)
                        VALUES (?, ?, ?, ?)
                    """, (
                        log_data.get('admin_id'),
                        log_data.get('subscription_type'),
                        log_data.get('username'),
                        log_data.get('link_id')
                    ))
                    await db.commit()
                    logger.info(f"📝 Лог подтверждения сохранен: {log_data.get('username')}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения лога подтверждения: {e}")
            raise e
    
    async def get_recent_confirmation_logs(self, limit: int = 10) -> List[Dict]:
        """Получение последних логов подтверждений"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        SELECT admin_id, subscription_type, username, link_id, timestamp
                        FROM confirmation_logs
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (limit,))
                    
                    rows = await cursor.fetchall()
                    await cursor.close()
                    
                    logs = []
                    for row in rows:
                        logs.append({
                            'admin_id': row[0],
                            'subscription_type': row[1],
                            'username': row[2],
                            'link_id': row[3],
                            'timestamp': row[4]
                        })
                    
                    logger.info(f"📊 Получено {len(logs)} логов подтверждений")
                    return logs
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения логов подтверждений: {e}")
            return []
    
    async def get_confirmation_stats(self) -> Dict:
        """Получение статистики подтверждений"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    # Общая статистика
                    cursor = await db.execute("SELECT COUNT(*) FROM confirmation_logs")
                    total = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Подтверждения сегодня
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM confirmation_logs 
                        WHERE DATE(timestamp) = DATE('now')
                    """)
                    today = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Подтверждения за неделю
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM confirmation_logs 
                        WHERE timestamp >= datetime('now', '-7 days')
                    """)
                    week = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Самая популярная подписка
                    cursor = await db.execute("""
                        SELECT subscription_type, COUNT(*) as count
                        FROM confirmation_logs
                        GROUP BY subscription_type
                        ORDER BY count DESC
                        LIMIT 1
                    """)
                    popular = await cursor.fetchone()
                    await cursor.close()
                    
                    popular_subscription = "нет данных"
                    if popular:
                        subscription_names = {
                            "25_stars": "⭐ 25 звезд",
                            "50_stars": "⭐ 50 звезд", 
                            "75_stars": "⭐ 75 звезд",
                            "100_stars": "⭐ 100 звезд",
                            "150_ton": "💎 150 TON",
                            "100_ton": "💎 100 TON",
                            "50_ton": "💎 50 TON"
                        }
                        display_name = subscription_names.get(popular[0], popular[0])
                        popular_subscription = f"{display_name} ({popular[1]} раз)"
                    
                    stats = {
                        'total': total,
                        'today': today,
                        'week': week,
                        'popular_subscription': popular_subscription
                    }
                    
                    logger.info(f"📈 Статистика подтверждений: {stats}")
                    return stats
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики подтверждений: {e}")
            return {}
    
    async def save_payment_confirmation(self, user_id: int, username: str, subscription_type: str, confirmed_by: int, invite_link: str):
        """Сохранение подтверждения оплаты"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("""
                        INSERT INTO payment_confirmations 
                        (user_id, username, subscription_type, confirmed_by, invite_link)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, username, subscription_type, confirmed_by, invite_link))
                    
                    await db.commit()
                    logger.info(f"✅ Подтверждение сохранено для @{username}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения подтверждения: {e}")
            raise e
    
    async def get_confirmation_history(self, limit: int = 10) -> List[Dict]:
        """Получение истории подтверждений"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        SELECT * FROM payment_confirmations
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))
                    
                    rows = await cursor.fetchall()
                    await cursor.close()
                    
                    history = []
                    columns = ['id', 'user_id', 'username', 'subscription_type', 'confirmed_by', 'invite_link', 'created_at']
                    
                    for row in rows:
                        record = dict(zip(columns, row))
                        history.append(record)
                    
                    logger.info(f"📊 Получена история подтверждений: {len(history)} записей")
                    return history
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения истории подтверждений: {e}")
            return []
    
    async def get_confirmation_stats(self) -> Dict:
        """Получение статистики подтверждений (исправленная версия)"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    # Общая статистика
                    cursor = await db.execute("SELECT COUNT(*) FROM payment_confirmations")
                    total_confirmations = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Подтверждения сегодня
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM payment_confirmations 
                        WHERE DATE(created_at) = DATE('now')
                    """)
                    today_confirmations = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Подтверждения за неделю
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM payment_confirmations 
                        WHERE created_at >= datetime('now', '-7 days')
                    """)
                    week_confirmations = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Подтверждения за месяц
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM payment_confirmations 
                        WHERE created_at >= datetime('now', '-30 days')
                    """)
                    month_confirmations = (await cursor.fetchone())[0]
                    await cursor.close()
                    
                    # Статистика по типам подписок
                    cursor = await db.execute("""
                        SELECT subscription_type, COUNT(*) as count
                        FROM payment_confirmations
                        GROUP BY subscription_type
                        ORDER BY count DESC
                    """)
                    by_subscription = await cursor.fetchall()
                    await cursor.close()
                    
                    # Формируем словарь статистики
                    stats = {
                        'total_confirmations': total_confirmations,
                        'today_confirmations': today_confirmations,
                        'week_confirmations': week_confirmations,
                        'month_confirmations': month_confirmations,
                        'by_subscription_type': dict(by_subscription)
                    }
                    
                    logger.info(f"📈 Статистика подтверждений обновлена: {stats}")
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
    
    async def save_pending_message(self, username: str, message: str, subscription_type: str, invite_link: str):
        """Сохранение отложенного сообщения для пользователя"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("""
                        INSERT INTO pending_messages 
                        (username, message, subscription_type, invite_link)
                        VALUES (?, ?, ?, ?)
                    """, (username, message, subscription_type, invite_link))
                    
                    await db.commit()
                    logger.info(f"📬 Отложенное сообщение сохранено для @{username}")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения отложенного сообщения: {e}")
            raise e
    
    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Получение пользователя по username"""
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("""
                        SELECT * FROM users WHERE username = ?
                    """, (username,))
                    
                    row = await cursor.fetchone()
                    await cursor.close()
                    
                    if row:
                        columns = ['id', 'username', 'first_name', 'last_name', 'created_at', 'referral_code']
                        return dict(zip(columns, row))
                    
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователя @{username}: {e}")
            return None
    
    async def check_subscription_access(self, user_id: int, subscription_amount: int, subscription_type: str) -> Dict:
        """
        Проверка доступа пользователя к каналу подписки
        """
        try:
            async with self._lock:
                async with aiosqlite.connect(self.db_path) as db:
                    # Проверяем наличие записи о подписке в базе данных
                    cursor = await db.execute("""
                        SELECT * FROM subscriptions 
                        WHERE user_id = ? AND subscription_type = ? AND amount = ? AND status = 'active'
                    """, (user_id, subscription_type, subscription_amount))
                    
                    row = await cursor.fetchone()
                    await cursor.close()
                    
                    if row:
                        return {
                            'has_access': True,
                            'subscription_data': dict(row)
                        }
                    else:
                        return {
                            'has_access': False,
                            'subscription_data': None
                        }
                        
        except Exception as e:
            logger.error(f"❌ Ошибка проверки доступа пользователя {user_id}: {e}")
            return {
                'has_access': False,
                'subscription_data': None
            }
    
    async def close(self):
        """Корректное закрытие соединения с базой данных"""
        logger.info("🔒 Асинхронная база данных закрыта")
