"""
Модели базы данных для PassiveNFT Bot
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

class DatabaseManager:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация таблиц базы данных"""
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
        
        # Таблица рефералов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                referral_code TEXT,
                commission_earned REAL DEFAULT 0.0,
                is_paid BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                FOREIGN KEY (referred_id) REFERENCES users (user_id)
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
        
        conn.commit()
        conn.close()
        logging.info("База данных инициализирована")
    
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
            logging.info(f"Создан новый пользователь: {user_id}")
        
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
        
        logging.info(f"Создана подписка {subscription_id} для пользователя {user_id}")
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
        logging.info(f"Обновлен статус оплаты для подписки {subscription_id}")
    
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
        """Получить статистику рефералов"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                u.username,
                u.referral_code,
                COUNT(r.id) as referrals_count,
                COUNT(CASE WHEN s.payment_status = 'paid' THEN 1 END) as paid_referrals,
                SUM(CASE WHEN s.payment_status = 'paid' THEN 
                    CASE 
                        WHEN s.subscription_type = '150_people' THEN 15.0
                        WHEN s.subscription_type = '100_people' THEN 10.0
                        WHEN s.subscription_type = '50_people' THEN 5.0
                        ELSE 0.0
                    END
                    ELSE 0.0
                END) as total_commission
            FROM users u
            LEFT JOIN referrals r ON u.user_id = r.referrer_id
            LEFT JOIN subscriptions s ON r.referred_id = s.user_id
            GROUP BY u.user_id, u.username, u.referral_code
            ORDER BY total_commission DESC
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