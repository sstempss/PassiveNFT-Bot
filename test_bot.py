#!/usr/bin/env python3
"""
Тесты для PassiveNFT Bot
"""
import unittest
import sqlite3
import tempfile
import os
from database import DatabaseManager
from config import Config

class TestDatabaseManager(unittest.TestCase):
    """Тесты для DatabaseManager"""
    
    def setUp(self):
        """Подготовка тестов"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.db = DatabaseManager(self.temp_db.name)
    
    def tearDown(self):
        """Очистка после тестов"""
        os.unlink(self.temp_db.name)
    
    def test_user_creation(self):
        """Тест создания пользователя"""
        referral_code = self.db.get_or_create_user(
            user_id=12345,
            username="test_user",
            first_name="Test",
            last_name="User"
        )
        
        self.assertIsNotNone(referral_code)
        self.assertEqual(len(referral_code), 8)
    
    def test_referral_code_generation(self):
        """Тест генерации реферальных кодов"""
        code1 = self.db.generate_referral_code()
        code2 = self.db.generate_referral_code()
        
        self.assertNotEqual(code1, code2)
        self.assertEqual(len(code1), 8)
    
    def test_subscription_creation(self):
        """Тест создания подписки"""
        # Создаем пользователя
        self.db.get_or_create_user(12345, "test", "Test", "User")
        
        # Создаем подписку
        sub_id = self.db.create_subscription(12345, "150_people")
        
        self.assertIsInstance(sub_id, int)
        self.assertGreater(sub_id, 0)
    
    def test_payment_status_update(self):
        """Тест обновления статуса оплаты"""
        # Создаем пользователя и подписку
        self.db.get_or_create_user(12345, "test", "Test", "User")
        sub_id = self.db.create_subscription(12345, "150_people")
        
        # Обновляем статус
        self.db.update_payment_status(sub_id, 150.0)
        
        # Проверяем в базе данных
        conn = sqlite3.connect(self.temp_db.name)
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status, amount_paid FROM subscriptions WHERE id = ?", (sub_id,))
        result = cursor.fetchone()
        conn.close()
        
        self.assertEqual(result[0], "paid")
        self.assertEqual(result[1], 150.0)
    
    def test_subscription_stats(self):
        """Тест получения статистики подписок"""
        # Создаем нескольких пользователей и подписок
        for i in range(5):
            self.db.get_or_create_user(1000 + i, f"user{i}", f"User{i}", "Test")
            self.db.create_subscription(1000 + i, "150_people")
        
        stats = self.db.get_subscription_stats()
        
        self.assertIn("150_people", stats)
        self.assertEqual(stats["150_people"]["total"], 5)

class TestConfig(unittest.TestCase):
    """Тесты для Config"""
    
    def test_config_loading(self):
        """Тест загрузки конфигурации"""
        config = Config()
        
        self.assertIsNotNone(config.BOT_TOKEN)
        self.assertIsNotNone(config.TON_WALLET_ADDRESS)
        self.assertIsInstance(config.SUBSCRIPTIONS, dict)
        self.assertIn("150_people", config.SUBSCRIPTIONS)
    
    def test_subscription_data(self):
        """Тест данных подписок"""
        config = Config()
        
        sub_150 = config.SUBSCRIPTIONS["150_people"]
        self.assertEqual(sub_150["nft_per_day"], 5)
        self.assertEqual(sub_150["gifts_per_day"], 4)
        self.assertEqual(sub_150["price"], 150)

def run_tests():
    """Запуск всех тестов"""
    print("🧪 Запуск тестов PassiveNFT Bot...")
    
    # Создаем test suite
    suite = unittest.TestSuite()
    
    # Добавляем тесты
    suite.addTest(unittest.makeSuite(TestDatabaseManager))
    suite.addTest(unittest.makeSuite(TestConfig))
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Выводим результат
    if result.wasSuccessful():
        print("✅ Все тесты пройдены успешно!")
        return True
    else:
        print(f"❌ {len(result.failures)} тестов провалено, {len(result.errors)} ошибок")
        return False

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)