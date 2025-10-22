"""
Конфигурация приложения HotSpot Shop
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Токены ботов
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "YOUR_ADMIN_BOT_TOKEN_HERE")

# ID администраторов
ADMIN_IDS = [123456789, 987654321]  # Замените на ваши Telegram ID

# URL веб-приложений
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-domain.com")
ADMIN_WEBAPP_URL = os.getenv("ADMIN_WEBAPP_URL", "https://admin.your-domain.com")

# Контакты
CONTACT_TELEGRAM = os.getenv("CONTACT_TELEGRAM", "@your_username")
CONTACT_VK = os.getenv("CONTACT_VK", "https://vk.com/your_username")
PAYMENT_PHONE = os.getenv("PAYMENT_PHONE", "+7 (999) 123-45-67")

# Данные для оплаты
PAYMENT_CARD_NUMBER = os.getenv("PAYMENT_CARD_NUMBER", "1234 5678 9012 3456")  # Номер карты для оплаты
PAYMENT_CARD_HOLDER = os.getenv("PAYMENT_CARD_HOLDER", "Your Name")  # Имя держателя карты
PAYMENT_CARD_BANK = os.getenv("PAYMENT_CARD_BANK", "Your Bank")  # Название банка

# Адреса самовывоза
CENTER_ADDR = os.getenv("CENTER_ADDR", "Центр")
MALL_ADDR = os.getenv("MALL_ADDR", "ТЦ")

# База данных
DATABASE_PATH = os.getenv("DATABASE_PATH", "shop.db")

# Сервер
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# Настройки кешбека по категориям
CASHBACK_RATES = {
    1: 3.0,  # Жидкости - 3%
    2: 3.0,  # Одноразки - 3%
    3: 3.0,  # Картриджи - 3%
    4: 2.0,  # POD-системы - 3%
}

# Стоимость доставки
DELIVERY_COST = 300

# Прочее
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

