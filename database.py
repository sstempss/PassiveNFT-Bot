"""
Модели базы данных для PassiveNFT Bot - ИСПРАВЛЕННАЯ ВЕРСИЯ
ИСПРАВЛЕНИЯ:
- Добавлена таблица pending_referrals
- Исправлена структура таблицы referrals
- Созданы индексы для оптимизации
- Добавлены методы для работы с реферальной системой
- Реализована система комиссий (10% от стоимости подписки)
"""
import sqlite3
import logging
from typing import Optional, List, Dict
from datetime import datetime
from dataclasses import dataclass

@dataclass
class User:
    user_id: int
    username: str
    first_name: str
    last_name: str
    registration_date: str
    referral_code: Optional[str] = None
    referred_by: Optional[int] = None

@dataclass
class Subscription:
    id: int
    user_id: int
    subscription_type: str  # "150_people", "100_people", "50_people"
    start_date: str
    end_date: str
    payment_status: str = "pending"  # "pending", "paid", "expired"
    payment_date: Optional[str] = None
    amount_paid: Optional[float] = None

@dataclass
class Referral:
    id: int
    referrer_id: int  # ID пользователя, который пригласил
    referred_id: int  # ID приглашенного пользователя
    referral_code: str
    commission_earned: float = 0.0
    is_paid: bool = False
    created_at: str = ""

@dataclass
class PendingReferral:
    id: int
    user_id: int
    referrer_id: int
    created_at: str

class DatabaseManager:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация таблиц базы данных - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registration_date TEXT,
                referral_code TEXT UNIQUE,
                referred_by INTEGER
            )
        """)
        
        # Таблица подписок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subscription_type TEXT,
                start_date TEXT,
                end_date TEXT,
                payment_status TEXT DEFAULT 'pending',
                payment_date TEXT,
                amount_paid REAL,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Таблица рефералов - ИСПРАВЛЕНАЯ СТРУКТУРА
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                referral_code TEXT UNIQUE,
                commission_earned REAL DEFAULT 0.0,
                is_paid BOOLEAN DEFAULT FALSE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                FOREIGN KEY (referred_id) REFERENCES users (user_id)
            )
        """)
        
        # НОВАЯ ТАБЛИЦА: Временное хранение рефереров
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                referrer_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Таблица платежей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subscription_id INTEGER,
                transaction_id TEXT,
                amount REAL,
                status TEXT,
                payment_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
            )
        """)
        
        # Создаем индексы для оптимизации запросов
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_referred ON referrals(referred_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_referrals_user ON pending_referrals(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_type ON subscriptions(subscription_type)")
        
        conn.commit()
        conn.close()
        logging.info("✅ База данных инициализирована с исправлениями")
    
    def get_or_create_user(self, user_id: int, username: str, first_name: str, last_name: str) -> str:
        """Получить или создать пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result:
            referral_code = result[0]
        else:
            # Создаем нового пользователя
            referral_code = self.generate_referral_code()
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name, last_name, registration_date, referral_code)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, datetime.now().isoformat(), referral_code))
            conn.commit()
            logging.info(f"✅ Создан новый пользователь: {user_id}")
        
        conn.close()
        return referral_code
    
    def generate_referral_code(self) -> str:
        """Генерация уникального реферального кода"""
        import random
        import string
        
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE referral_code = ?", (code,))
            count = cursor.fetchone()[0]
            conn.close()
            
            if count == 0:
                return code
    
    def get_user_by_referral_code(self, code: str) -> Optional[int]:
        """Получить user_id по реферальному коду"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE referral_code = ?", (code,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def create_subscription(self, user_id: int, subscription_type: str) -> int:
        """Создать подписку"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        from datetime import datetime, timedelta
        start_date = datetime.now()
        end_date = start_date + timedelta(days=30)  # 30 дней
        
        cursor.execute("""
            INSERT INTO subscriptions (user_id, subscription_type, start_date, end_date)
            VALUES (?, ?, ?, ?)
        """, (user_id, subscription_type, start_date.isoformat(), end_date.isoformat()))
        
        subscription_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logging.info(f"✅ Создана подписка {subscription_id} для пользователя {user_id}")
        return subscription_id
    
    def update_payment_status(self, subscription_id: int, amount: float):
        """Обновить статус оплаты"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE subscriptions 
            SET payment_status = 'paid', 
                payment_date = ?, 
                amount_paid = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), amount, subscription_id))
        
        conn.commit()
        conn.close()
        logging.info(f"✅ Обновлен статус оплаты для подписки {subscription_id}")
    
    # НОВЫЕ МЕТОДЫ ДЛЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ
    
    def save_pending_referral(self, user_id: int, referrer_id: int):
        """Сохранение информации о временном рефере"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO pending_referrals (user_id, referrer_id, created_at) 
                    VALUES (?, ?, ?)
                """, (user_id, referrer_id, datetime.now().isoformat()))
                conn.commit()
                logging.info(f"✅ Сохранен временный реферер {referrer_id} для пользователя {user_id}")
        except Exception as e:
            logging.error(f"❌ Ошибка сохранения временного реферера: {e}")
            raise
    
    def get_pending_referrer(self, user_id: int) -> Optional[int]:
        """Получение ожидающего реферера для пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT referrer_id FROM pending_referrals WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logging.error(f"❌ Ошибка получения ожидающего реферера: {e}")
            return None
    
    def remove_pending_referral(self, user_id: int):
        """Удаление записи об ожидающем рефере"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM pending_referrals WHERE user_id = ?", (user_id,))
                conn.commit()
                logging.info(f"✅ Удален временный реферер для пользователя {user_id}")
        except Exception as e:
            logging.error(f"❌ Ошибка удаления временного реферера: {e}")
            raise
    
    def add_referral(self, referrer_id: int, referred_user_id: int) -> bool:
        """ИСПРАВЛЕННОЕ добавление реферала в базу данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем, что пользователь еще не добавлен как реферал
                cursor.execute(
                    "SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND referred_id = ?",
                    (referrer_id, referred_user_id)
                )
                if cursor.fetchone()[0] > 0:
                    logging.info(f"ℹ️ Реферал {referred_user_id} для {referrer_id} уже существует")
                    return True
                
                # ИСПРАВЛЕНО: Добавляем только один раз без дублирования
                referral_code = str(referred_user_id)  # Используем ID как код
                cursor.execute("""
                    INSERT INTO referrals (referrer_id, referred_id, referral_code, commission_earned, is_paid)
                    VALUES (?, ?, ?, ?, ?)
                """, (referrer_id, referred_user_id, referral_code, 0.0, False))
                
                conn.commit()
                logging.info(f"✅ Добавлен реферал {referred_user_id} для реферера {referrer_id}")
                return True
        except Exception as e:
            logging.error(f"❌ Ошибка добавления реферала: {e}")
            return False
    
    def calculate_commission(self, subscription_type: str) -> float:
        """Расчет комиссии для типа подписки - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        commission_rates = {
            "150_people": 15.0,  # 10% от 150 TON
            "100_people": 10.0,  # 10% от 100 TON
            "50_people": 5.0     # 10% от 50 TON
        }
        return commission_rates.get(subscription_type, 0.0)
    
    def add_referral_earnings(self, referrer_id: int, commission: float, subscription_type: str):
        """Начисление доходов рефереру - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Обновляем commission_earned в таблице referrals для этого реферера
                cursor.execute("""
                    UPDATE referrals 
                    SET commission_earned = commission_earned + ?
                    WHERE referrer_id = ?
                """, (commission, referrer_id))
                
                conn.commit()
                logging.info(f"✅ Начислена комиссия {commission} TON рефереру {referrer_id} за {subscription_type}")
        except Exception as e:
            logging.error(f"❌ Ошибка начисления комиссии: {e}")
            raise
    
    def get_subscription_stats(self) -> Dict[str, Dict]:
        """Получить статистику подписок"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        for sub_type in ["150_people", "100_people", "50_people"]:
            cursor.execute("""
                SELECT payment_status, COUNT(*) 
                FROM subscriptions 
                WHERE subscription_type = ? 
                GROUP BY payment_status
            """, (sub_type,))
            
            results = cursor.fetchall()
            stats[sub_type] = {"total": 0, "paid": 0, "pending": 0}
            
            for status, count in results:
                stats[sub_type]["total"] += count
                if status == "paid":
                    stats[sub_type]["paid"] = count
                else:
                    stats[sub_type]["pending"] = count
        
        conn.close()
        return stats
    
    def get_subscribers(self) -> List[Dict]:
        """Получить список подписчиков"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT u.username, u.first_name, s.subscription_type, s.payment_status
            FROM users u
            JOIN subscriptions s ON u.user_id = s.user_id
            WHERE s.payment_status = 'paid'
            ORDER BY u.username
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        return [{"username": row[0], "name": row[1], "subscription": row[2]} for row in results]
    
    def get_referral_stats(self) -> List[Dict]:
        """ИСПРАВЛЕННАЯ статистика рефералов"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                u.username,
                u.referral_code,
                COUNT(r.id) as referrals_count,
                COUNT(CASE WHEN s.payment_status = 'paid' THEN 1 END) as paid_referrals,
                COALESCE(SUM(r.commission_earned), 0) as total_commission
            FROM users u
            LEFT JOIN referrals r ON u.user_id = r.referrer_id
            LEFT JOIN subscriptions s ON r.referred_id = s.user_id
            GROUP BY u.user_id, u.username, u.referral_code
            HAVING referrals_count > 0
            ORDER BY total_commission DESC, referrals_count DESC
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                "username": row[0],
                "referral_code": row[1], 
                "total_referrals": row[2],
                "paid_referrals": row[3],
                "commission": row[4]
            }
            for row in results
        ]
    
    def get_user_referral_stats(self, user_id: int) -> Optional[str]:
        """ИСПРАВЛЕННАЯ статистика рефералов для конкретного пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        COUNT(r.id) as total_referrals,
                        COUNT(CASE WHEN s.payment_status = 'paid' THEN 1 END) as paid_referrals,
                        COALESCE(SUM(r.commission_earned), 0) as total_earnings
                    FROM referrals r
                    LEFT JOIN subscriptions s ON r.referred_id = s.user_id
                    WHERE r.referrer_id = ?
                """, (user_id,))
                
                result = cursor.fetchone()
                if result and result[0] > 0:  # Есть рефералы
                    total, paid, earnings = result
                    return f"""📊 Ваша реферальная статистика:
👥 Всего рефералов: {total}
✅ Оплативших рефералов: {paid}
💰 Общий доход: {earnings} TON"""
                return None
        except Exception as e:
            logging.error(f"❌ Ошибка получения статистики рефералов: {e}")
            return None
    
    def cleanup_old_pending_referrals(self, days: int = 7):
        """Очистка старых записей pending_referrals"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                from datetime import datetime, timedelta
                
                cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                cursor.execute("""
                    DELETE FROM pending_referrals 
                    WHERE created_at < ?
                """, (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                logging.info(f"✅ Удалено {deleted_count} старых записей pending_referrals")
        except Exception as e:
            logging.error(f"❌ Ошибка очистки pending_referrals: {e}")
    
    def get_all_users_count(self) -> int:
        """Получить общее количество пользователей"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                return cursor.fetchone()[0]
        except Exception as e:
            logging.error(f"❌ Ошибка получения количества пользователей: {e}")
            return 0
    
    def get_total_referrals_count(self) -> int:
        """Получить общее количество рефералов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM referrals")
                return cursor.fetchone()[0]
        except Exception as e:
            logging.error(f"❌ Ошибка получения количества рефералов: {e}")
            return 0
    
    def get_total_commission_earned(self) -> float:
        """Получить общую сумму начисленных комиссий"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COALESCE(SUM(commission_earned), 0) FROM referrals")
                return cursor.fetchone()[0]
        except Exception as e:
            logging.error(f"❌ Ошибка получения общей суммы комиссий: {e}")
            return 0.0
