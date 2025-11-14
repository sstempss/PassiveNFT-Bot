#!/usr/bin/env python3
"""
Утилиты для администрирования PassiveNFT Bot
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from database import DatabaseManager
from config import Config

class AdminUtilities:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.db = DatabaseManager(db_path)
        self.config = Config()
    
    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """Создать резервную копию базы данных"""
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_{timestamp}.db"
        
        try:
            # Копируем файл БД
            import shutil
            shutil.copy2(self.db_path, backup_path)
            print(f"✅ Резервная копия создана: {backup_path}")
            return backup_path
        except Exception as e:
            print(f"❌ Ошибка создания резервной копии: {e}")
            return ""
    
    def export_user_data(self, user_id: int) -> Dict:
        """Экспорт данных пользователя"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем данные пользователя
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
            
            if not user_data:
                return {"error": "Пользователь не найден"}
            
            # Получаем подписки пользователя
            cursor.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))
            subscriptions = cursor.fetchall()
            
            # Получаем реферальные данные
            cursor.execute("SELECT * FROM referrals WHERE referred_id = ?", (user_id,))
            referrals_as_referred = cursor.fetchall()
            
            cursor.execute("SELECT * FROM referrals WHERE referrer_id = ?", (user_id,))
            referrals_as_referrer = cursor.fetchall()
            
            conn.close()
            
            return {
                "user_id": user_id,
                "user_data": user_data,
                "subscriptions": subscriptions,
                "referrals_as_referred": referrals_as_referred,
                "referrals_as_referrer": referrals_as_referrer,
                "export_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Ошибка экспорта: {e}"}
    
    def get_payment_stats(self) -> Dict:
        """Получить статистику платежей"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Общая сумма платежей
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_payments,
                    SUM(amount_paid) as total_amount,
                    AVG(amount_paid) as avg_amount,
                    payment_date
                FROM subscriptions 
                WHERE payment_status = 'paid'
                GROUP BY DATE(payment_date)
                ORDER BY payment_date DESC
            """)
            
            daily_stats = cursor.fetchall()
            
            # Статистика по типам подписок
            cursor.execute("""
                SELECT 
                    subscription_type,
                    COUNT(*) as count,
                    SUM(amount_paid) as total_amount
                FROM subscriptions 
                WHERE payment_status = 'paid'
                GROUP BY subscription_type
            """)
            
            type_stats = cursor.fetchall()
            
            conn.close()
            
            return {
                "daily_payments": daily_stats,
                "subscription_type_stats": type_stats,
                "report_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Ошибка получения статистики: {e}"}
    
    def clean_expired_subscriptions(self) -> int:
        """Очистить истекшие подписки"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Помечаем истекшие подписки как expired
            cursor.execute("""
                UPDATE subscriptions 
                SET payment_status = 'expired'
                WHERE end_date < datetime('now') AND payment_status = 'paid'
            """)
            
            expired_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            print(f"✅ Помечено {expired_count} истекших подписок")
            return expired_count
            
        except Exception as e:
            print(f"❌ Ошибка очистки подписок: {e}")
            return 0
    
    def calculate_commissions(self) -> Dict:
        """Рассчитать комиссии для рефереров"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем все оплаченные подписки с реферальными связями
            cursor.execute("""
                SELECT 
                    r.referrer_id,
                    u.referral_code,
                    s.subscription_type,
                    s.amount_paid,
                    s.payment_date
                FROM referrals r
                JOIN subscriptions s ON r.referred_id = s.user_id
                JOIN users u ON r.referrer_id = u.user_id
                WHERE s.payment_status = 'paid'
            """)
            
            paid_subscriptions = cursor.fetchall()
            
            # Рассчитываем комиссии
            commission_rates = {
                "150_people": 0.10,  # 10% от 150 TON = 15 TON
                "100_people": 0.10,  # 10% от 100 TON = 10 TON
                "50_people": 0.10    # 10% от 50 TON = 5 TON
            }
            
            commissions = {}
            
            for referrer_id, referral_code, sub_type, amount_paid, payment_date in paid_subscriptions:
                if referrer_id not in commissions:
                    commissions[referrer_id] = {
                        "referral_code": referral_code,
                        "total_commission": 0.0,
                        "payments": []
                    }
                
                # Рассчитываем комиссию (10% от суммы подписки)
                commission_rate = commission_rates.get(sub_type, 0.10)
                commission = amount_paid * commission_rate
                
                commissions[referrer_id]["total_commission"] += commission
                commissions[referrer_id]["payments"].append({
                    "subscription_type": sub_type,
                    "amount_paid": amount_paid,
                    "commission": commission,
                    "payment_date": payment_date
                })
            
            # Обновляем комиссии в базе данных
            for referrer_id, data in commissions.items():
                cursor.execute("""
                    UPDATE referrals 
                    SET commission_earned = ?
                    WHERE referrer_id = ?
                """, (data["total_commission"], referrer_id))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Рассчитаны комиссии для {len(commissions)} рефереров")
            return {
                "total_referrers": len(commissions),
                "total_commission_paid": sum(data["total_commission"] for data in commissions.values()),
                "commissions": commissions,
                "calculation_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Ошибка расчета комиссий: {e}")
            return {"error": str(e)}
    
    def generate_report(self, report_type: str = "full") -> str:
        """Генерация отчета"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if report_type == "full":
            # Полный отчет
            stats = self.db.get_subscription_stats()
            people = self.db.get_subscribers()
            referrals = self.db.get_referral_stats()
            payments = self.get_payment_stats()
            
            report = f"""
ОТЧЕТ PASIVENFT BOT
Дата генерации: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

=== СТАТИСТИКА ПОДПИСОК ===
"""
            for sub_type, data in stats.items():
                sub_name = self.config.SUBSCRIPTIONS[sub_type]["name"]
                report += f"{sub_name}:\n"
                report += f"  Всего: {data['total']}\n"
                report += f"  Оплачено: {data['paid']}\n"
                report += f"  В ожидании: {data['pending']}\n\n"
            
            report += f"""
=== УЧАСТНИКИ ({len(people)} человек) ===
"""
            for person in people:
                report += f"- {person['username']} ({person['subscription']})\n"
            
            report += f"""
=== РЕФЕРАЛЬНАЯ СИСТЕМА ===
"""
            for ref in referrals:
                if ref["total_referrals"] > 0:
                    report += f"- {ref['username']}: {ref['total_referrals']} рефералов, {ref['commission']} TON\n"
            
        else:
            # Простой отчет
            report = f"ПРОСТОЙ ОТЧЕТ PASIVENFT BOT\nДата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # Сохраняем отчет
        report_filename = f"report_{report_type}_{timestamp}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ Отчет сохранен: {report_filename}")
        return report_filename
    
    def reset_database(self) -> bool:
        """Сброс базы данных (ОСТОРОЖНО!)"""
        response = input("⚠️  Это удалит ВСЕ данные! Введите 'DELETE' для подтверждения: ")
        
        if response == "DELETE":
            try:
                os.remove(self.db_path)
                print("✅ База данных удалена")
                
                # Пересоздаем БД
                self.db.init_database()
                print("✅ База данных пересоздана")
                return True
            except Exception as e:
                print(f"❌ Ошибка сброса БД: {e}")
                return False
        else:
            print("❌ Операция отменена")
            return False

def main():
    """Интерфейс командной строки для утилит"""
    utils = AdminUtilities()
    
    print("🛠️  Утилиты администрирования PassiveNFT Bot")
    print("1. Создать резервную копию БД")
    print("2. Экспорт данных пользователя")
    print("3. Статистика платежей")
    print("4. Очистить истекшие подписки")
    print("5. Рассчитать комиссии")
    print("6. Генерация отчета")
    print("7. Сброс БД (ОСТОРОЖНО!)")
    print("0. Выход")
    
    while True:
        choice = input("\nВыберите действие: ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            utils.backup_database()
        elif choice == "2":
            user_id = input("Введите User ID: ")
            try:
                data = utils.export_user_data(int(user_id))
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except ValueError:
                print("❌ Неверный User ID")
        elif choice == "3":
            stats = utils.get_payment_stats()
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        elif choice == "4":
            utils.clean_expired_subscriptions()
        elif choice == "5":
            utils.calculate_commissions()
        elif choice == "6":
            report_type = input("Тип отчета (full/simple): ").strip() or "full"
            utils.generate_report(report_type)
        elif choice == "7":
            utils.reset_database()
        else:
            print("❌ Неверный выбор")

if __name__ == "__main__":
    main()