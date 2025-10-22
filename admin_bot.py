"""
Админский бот для HotSpot Shop v2.0
Полноценное управление заказами, клиентами, промокодами
Расширенная статистика и удобные фишки
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import json

from config import ADMIN_BOT_TOKEN, BOT_TOKEN, ADMIN_IDS, DATABASE_PATH
from database import Database

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=ADMIN_BOT_TOKEN)  # Админский бот
client_bot = Bot(token=BOT_TOKEN)  # Клиентский бот для рассылки
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database(DATABASE_PATH)

# Хранилище для последних ID заказов
last_checked_order_id = 0


# ========== Вспомогательные функции ==========

def escape_html(text: str) -> str:
    """Экранирование HTML-символов для Telegram"""
    if not text:
        return text
    return (text
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;'))


# ========== FSM States ==========

class PromoCreate(StatesGroup):
    """Создание промокода"""
    code = State()
    type = State()
    value = State()
    max_uses = State()
    confirm = State()


class ClientManage(StatesGroup):
    """Управление клиентом"""
    select_client = State()
    action = State()
    value = State()


class BroadcastMessage(StatesGroup):
    """Рассылка сообщений"""
    text = State()
    confirm = State()


class DiscountCreate(StatesGroup):
    """Создание скидки"""
    name = State()
    type = State()
    value = State()
    target_id = State()
    min_purchase = State()


class StockManage(StatesGroup):
    """Управление наличием товара"""
    select_brand = State()
    select_product = State()
    update_variants = State()
    add_flavor_name = State()
    add_flavor_quantity = State()


# ========== Клавиатуры ==========

def get_main_keyboard():
    """Главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
            InlineKeyboardButton(text="📦 Заказы", callback_data="orders")
        ],
        [
            InlineKeyboardButton(text="👥 Клиенты", callback_data="clients"),
            InlineKeyboardButton(text="🎟️ Промокоды", callback_data="promos")
        ],
        [
            InlineKeyboardButton(text="💸 Скидки", callback_data="discounts"),
            InlineKeyboardButton(text="➕ Скидка", callback_data="discount_create")
        ],
        [
            InlineKeyboardButton(text="➕ Промокод", callback_data="promo_create"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="broadcast")
        ],
        [
            InlineKeyboardButton(text="📦 Наличие товара", callback_data="stock_manage"),
            InlineKeyboardButton(text="📈 Детальная статистика", callback_data="stats_detailed")
        ],
        [
            InlineKeyboardButton(text="🌐 Админ-панель", url="https://admin.hotspotovich.shop")
        ],
        [
            InlineKeyboardButton(text="🛠️ Связь с разработчиком", callback_data="contact_developer")
        ]
    ])
    return keyboard


def get_order_keyboard(order_id: int, status: str, has_screenshot: bool = False, payment_confirmed: bool = False):
    """Клавиатура для заказа"""
    buttons = []
    
    # Главные действия в зависимости от статуса (большие кнопки)
    if status == 'pending':
        buttons.append([InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data=f"order_status_confirmed_{order_id}")])
        buttons.append([InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"order_status_cancelled_{order_id}")])
    elif status == 'confirmed':
        buttons.append([InlineKeyboardButton(text="🎉 Выполнить заказ (завершить)", callback_data=f"order_status_completed_{order_id}")])
        buttons.append([InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"order_status_cancelled_{order_id}")])
    elif status == 'completed':
        buttons.append([InlineKeyboardButton(text="✅ Заказ уже выполнен", callback_data="noop")])
    
    # Скриншот оплаты
    if has_screenshot:
        screenshot_button = []
        screenshot_button.append(InlineKeyboardButton(text="📸 Скриншот", callback_data=f"order_screenshot_{order_id}"))
        
        # Подтверждение оплаты
        if not payment_confirmed and status != 'completed':
            screenshot_button.append(InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"order_confirm_payment_{order_id}"))
        
        buttons.append(screenshot_button)
    
    # Связаться с клиентом
    buttons.append([InlineKeyboardButton(text="💬 Связаться с клиентом", callback_data=f"order_contact_{order_id}")])
    
    # Команды (слэш-команды сохранены как альтернатива)
    buttons.append([InlineKeyboardButton(text="📋 Слэш-команды", callback_data=f"order_commands_{order_id}")])
    
    # Назад
    buttons.append([InlineKeyboardButton(text="🔙 К списку заказов", callback_data="orders")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def get_orders_list_keyboard(orders):
    """Клавиатура со списком заказов и фильтрами"""
    buttons = []
    
    # Добавляем кнопки для каждого заказа (по 3 в ряд)
    order_buttons = []
    for order in orders:
        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'completed': '🎉',
            'cancelled': '❌'
        }.get(order['status'], '❓')
        
        button_text = f"{status_emoji} #{order['id']}"
        order_buttons.append(InlineKeyboardButton(
            text=button_text,
            callback_data=f"view_order_{order['id']}"
        ))
    
    # Группируем по 3 кнопки в ряд
    for i in range(0, len(order_buttons), 3):
        buttons.append(order_buttons[i:i+3])
    
    # Фильтры
    buttons.append([
        InlineKeyboardButton(text="⏳ Ожидают", callback_data="orders_filter_pending"),
        InlineKeyboardButton(text="✅ Подтверждены", callback_data="orders_filter_confirmed")
    ])
    buttons.append([
        InlineKeyboardButton(text="📅 Сегодня", callback_data="orders_filter_today"),
        InlineKeyboardButton(text="📆 Неделя", callback_data="orders_filter_week")
    ])
    
    # Назад в главное меню
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def get_orders_filter_keyboard():
    """Клавиатура фильтров заказов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏳ Ожидают", callback_data="orders_filter_pending"),
            InlineKeyboardButton(text="✅ Подтверждённые", callback_data="orders_filter_confirmed")
        ],
        [
            InlineKeyboardButton(text="🎉 Завершённые", callback_data="orders_filter_completed"),
            InlineKeyboardButton(text="❌ Отменённые", callback_data="orders_filter_cancelled")
        ],
        [
            InlineKeyboardButton(text="📅 Сегодня", callback_data="orders_filter_today"),
            InlineKeyboardButton(text="📆 Неделя", callback_data="orders_filter_week")
        ],
        [
            InlineKeyboardButton(text="🔄 Все заказы", callback_data="orders")
        ],
        [
            InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_clients_keyboard(page: int = 0):
    """Клавиатура списка клиентов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Топ клиенты", callback_data="clients_top"),
            InlineKeyboardButton(text="🆕 Новые", callback_data="clients_new")
        ],
        [
            InlineKeyboardButton(text="💰 По балансу", callback_data="clients_balance"),
            InlineKeyboardButton(text="📦 По заказам", callback_data="clients_orders")
        ],
        [
            InlineKeyboardButton(text="🔍 Найти клиента", callback_data="clients_search")
        ],
        [
            InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
        ]
    ])
    return keyboard


def get_client_actions_keyboard(telegram_id: int):
    """Клавиатура действий с клиентом"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"client_balance_{telegram_id}"),
            InlineKeyboardButton(text="📦 Заказы", callback_data=f"client_orders_{telegram_id}")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"client_stats_{telegram_id}"),
            InlineKeyboardButton(text="❌ Заблокировать", callback_data=f"client_block_{telegram_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 К списку клиентов", callback_data="clients")
        ]
    ])
    return keyboard


def get_promo_keyboard(promo_id: int):
    """Клавиатура для промокода"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"promo_delete_{promo_id}"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"promo_stats_{promo_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 К промокодам", callback_data="promos")
        ]
    ])
    return keyboard


def get_cancel_keyboard():
    """Клавиатура отмены"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")]
    ])
    return keyboard


# ========== Команды ==========

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет доступа к этому боту")
        return
    
    await state.clear()
    await message.answer(
        "🔥 <b>HotSpot Admin Bot v3.0</b>\n\n"
        "🎯 <b>Основные функции:</b>\n"
        "• 📦 Управление заказами с детальным чеком\n"
        "• 👥 Управление клиентами (баланс, профиль)\n"
        "• 🛍️ Управление товарами и вариантами\n"
        "• 🏷️ Категории и бренды\n\n"
        "💰 <b>Скидки и промо:</b>\n"
        "• 🎟️ Создание промокодов (%, ₽, баланс)\n"
        "• 💸 Автоматические скидки на категории\n"
        "• 🎁 Фиксированные скидки от суммы\n\n"
        "📊 <b>Аналитика:</b>\n"
        "• 📈 Расширенная статистика продаж\n"
        "• 💵 Учёт баланса и кешбэка\n"
        "• 🧾 Детальные чеки заказов\n\n"
        "📢 <b>Коммуникация:</b>\n"
        "• 📣 Рассылка сообщений клиентам\n"
        "• 🔔 Автоуведомления о новых заказах\n"
        "• 💬 Прямая связь с клиентами\n\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Команда /stats"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await show_stats(message)


@dp.message(Command("order"))
async def cmd_order(message: Message):
    """Команда /order <id> - просмотр заказа"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /order <номер_заказа>")
        return
    
    try:
        order_id = int(args[1])
        await show_order_detail(message, order_id)
    except ValueError:
        await message.answer("❌ Неверный формат номера заказа")
    except Exception as e:
        logger.error(f"Error showing order: {e}")
        await message.answer("❌ Ошибка получения заказа")


@dp.message(Command("client"))
async def cmd_client(message: Message):
    """Команда /client <telegram_id> - просмотр клиента"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /client <telegram_id>")
        return
    
    try:
        telegram_id = int(args[1])
        await show_client_detail(message, telegram_id)
    except ValueError:
        await message.answer("❌ Неверный формат telegram_id")
    except Exception as e:
        logger.error(f"Error showing client: {e}")
        await message.answer("❌ Ошибка получения клиента")


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущей операции"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.clear()
    await message.answer("❌ Операция отменена", reply_markup=get_main_keyboard())


# ========== Callback handlers - Главное меню ==========

@dp.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    """Главное меню"""
    await state.clear()
    await callback.message.edit_text(
        "🔥 <b>HotSpot Admin Bot</b>\n\nВыберите действие:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню (алиас)"""
    await state.clear()
    await callback.message.edit_text(
        "🔥 <b>HotSpot Admin Bot</b>\n\nВыберите действие:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена операции"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Операция отменена\n\nВыберите действие:",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data == "contact_developer")
async def callback_contact_developer(callback: CallbackQuery):
    """Связь с разработчиком"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать разработчику", url="https://t.me/x32asm")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(
        "🛠️ <b>Связь с разработчиком</b>\n\n"
        "Если у вас возникли вопросы, проблемы или предложения\n"
        "по работе бота, свяжитесь с разработчиком.\n\n"
        "📱 Telegram: @x32asm\n\n"
        "<i>Пример сообщения:</i>\n"
        "\"Привет! У меня проблема с админ-ботом...\"",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# ========== Callback handlers - Статистика ==========

@dp.callback_query(F.data == "stats")
async def callback_stats(callback: CallbackQuery):
    """Показать статистику"""
    await callback.answer()
    await show_stats(callback.message)


@dp.callback_query(F.data == "stats_detailed")
async def callback_stats_detailed(callback: CallbackQuery):
    """Показать детальную статистику"""
    await callback.answer()
    await show_detailed_stats(callback.message)


# ========== Callback handlers - Заказы ==========

@dp.callback_query(F.data == "orders")
async def callback_orders(callback: CallbackQuery):
    """Показать заказы"""
    await callback.answer()
    await show_orders(callback.message)


@dp.callback_query(F.data.startswith("view_order_"))
async def callback_view_order(callback: CallbackQuery):
    """Просмотр конкретного заказа"""
    order_id = int(callback.data.split("_")[2])
    await callback.answer()
    await show_order_detail(callback.message, order_id, edit=True)


@dp.callback_query(F.data.startswith("orders_filter_"))
async def callback_orders_filter(callback: CallbackQuery):
    """Фильтр заказов"""
    filter_type = callback.data.replace("orders_filter_", "")
    await callback.answer()
    await show_orders_filtered(callback.message, filter_type)


@dp.callback_query(F.data.startswith("order_status_"))
async def callback_order_status(callback: CallbackQuery):
    """Изменить статус заказа"""
    parts = callback.data.split("_")
    new_status = parts[2]
    order_id = int(parts[3])
    
    try:
        if new_status == 'completed':
            # Завершить заказ и начислить кешбек
            db.complete_order_and_add_cashback(order_id)
        else:
            # Используем метод update_order_status который вернёт баланс при отмене
            db.update_order_status(order_id, new_status)
        
        status_names = {
            'confirmed': '✅ Заказ подтверждён',
            'completed': '🎉 Заказ завершён, кешбек начислен',
            'cancelled': '❌ Заказ отменён'
        }
        
        await callback.answer(status_names.get(new_status, "Статус изменён"), show_alert=True)
        
        # Обновить сообщение
        await show_order_detail(callback.message, order_id, edit=True)
        
    except Exception as e:
        logger.error(f"Error changing order status: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("order_screenshot_"))
async def callback_order_screenshot(callback: CallbackQuery):
    """Показать скриншот оплаты"""
    order_id = int(callback.data.split("_")[2])
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_screenshot FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()
        
        if order and order['payment_screenshot']:
            screenshot_url = f"https://hotspotovich.shop{order['payment_screenshot']}"
            await callback.message.answer_photo(
                photo=screenshot_url,
                caption=f"📸 Скриншот оплаты для заказа #{order_id}"
            )
            await callback.answer()
        else:
            await callback.answer("❌ Скриншот не найден", show_alert=True)
    except Exception as e:
        logger.error(f"Error showing screenshot: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("order_confirm_payment_"))
async def callback_order_confirm_payment(callback: CallbackQuery):
    """Подтвердить оплату заказа"""
    order_id = int(callback.data.split("_")[3])
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET payment_confirmed = 1 WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()
        
        await callback.answer("✅ Оплата подтверждена!", show_alert=True)
        await show_order_detail(callback.message, order_id, edit=True)
        
    except Exception as e:
        logger.error(f"Error confirming payment: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("order_contact_"))
async def callback_order_contact(callback: CallbackQuery):
    """Получить ссылку на клиента"""
    order_id = int(callback.data.split("_")[2])
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.telegram_id, u.username 
            FROM orders o 
            JOIN users u ON o.user_id = u.id 
            WHERE o.id = ?
        """, (order_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            if result['username']:
                link = f"https://t.me/{result['username']}"
                await callback.answer(f"Открываю чат с @{result['username']}", show_alert=True)
                await callback.message.answer(f"💬 Связаться с клиентом: {link}")
            else:
                await callback.answer(f"ID клиента: {result['telegram_id']}", show_alert=True)
        else:
            await callback.answer("❌ Клиент не найден", show_alert=True)
    except Exception as e:
        logger.error(f"Error getting client contact: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("order_commands_"))
async def callback_order_commands(callback: CallbackQuery):
    """Показать доступные команды для заказа"""
    order_id = int(callback.data.split("_")[2])
    
    help_text = (
        f"📋 <b>Команды для заказа #{order_id}:</b>\n\n"
        f"<code>/order {order_id}</code> - просмотр заказа\n\n"
        f"<b>Альтернативные команды:</b>\n"
        f"• /confirm {order_id} - подтвердить\n"
        f"• /complete {order_id} - завершить\n"
        f"• /cancel_order {order_id} - отменить\n\n"
        f"💡 <i>Проще использовать кнопки выше!</i>"
    )
    
    await callback.answer()
    await callback.message.answer(help_text, parse_mode="HTML")


@dp.callback_query(F.data == "noop")
async def callback_noop(callback: CallbackQuery):
    """Пустой callback для неактивных кнопок"""
    await callback.answer()


# ========== Callback handlers - Клиенты ==========

@dp.callback_query(F.data == "clients")
async def callback_clients(callback: CallbackQuery):
    """Показать клиентов"""
    await callback.answer()
    await show_clients_menu(callback.message)


@dp.callback_query(F.data == "clients_top")
async def callback_clients_top(callback: CallbackQuery):
    """Топ клиенты"""
    await callback.answer()
    await show_clients_top(callback.message)


@dp.callback_query(F.data == "clients_new")
async def callback_clients_new(callback: CallbackQuery):
    """Новые клиенты"""
    await callback.answer()
    await show_clients_new(callback.message)


@dp.callback_query(F.data == "clients_balance")
async def callback_clients_balance(callback: CallbackQuery):
    """Клиенты по балансу"""
    await callback.answer()
    await show_clients_by_balance(callback.message)


@dp.callback_query(F.data == "clients_orders")
async def callback_clients_orders(callback: CallbackQuery):
    """Клиенты по заказам"""
    await callback.answer()
    await show_clients_by_orders(callback.message)


@dp.callback_query(F.data.startswith("client_detail_"))
async def callback_client_detail(callback: CallbackQuery):
    """Детали клиента"""
    telegram_id = int(callback.data.split("_")[2])
    await callback.answer()
    await show_client_detail(callback.message, telegram_id, edit=True)


@dp.callback_query(F.data.startswith("client_orders_"))
async def callback_client_orders(callback: CallbackQuery):
    """Заказы клиента"""
    telegram_id = int(callback.data.split("_")[2])
    await callback.answer()
    await show_client_orders(callback.message, telegram_id)


@dp.callback_query(F.data.startswith("client_stats_"))
async def callback_client_stats(callback: CallbackQuery):
    """Статистика клиента"""
    telegram_id = int(callback.data.split("_")[2])
    await callback.answer()
    await show_client_stats(callback.message, telegram_id)


@dp.callback_query(F.data.startswith("client_balance_"))
async def callback_client_balance(callback: CallbackQuery, state: FSMContext):
    """Изменить баланс клиента"""
    telegram_id = int(callback.data.split("_")[2])
    await callback.answer()
    
    await callback.message.answer(
        f"💰 Изменение баланса клиента {telegram_id}\n\n"
        "Введите сумму для начисления (положительное число) или списания (отрицательное число):\n\n"
        "Например: 500 или -200",
        reply_markup=get_cancel_keyboard()
    )
    
    await state.set_state(ClientManage.value)
    await state.update_data(telegram_id=telegram_id, action='balance')


# ========== Callback handlers - Промокоды ==========

@dp.callback_query(F.data == "promos")
async def callback_promos(callback: CallbackQuery):
    """Показать промокоды"""
    await callback.answer()
    await show_promos(callback.message)


@dp.callback_query(F.data == "promo_create")
async def callback_promo_create(callback: CallbackQuery, state: FSMContext):
    """Начать создание промокода"""
    await callback.answer()
    await callback.message.answer(
        "➕ <b>Создание промокода</b>\n\n"
        "Введите код промокода (например: SALE2024):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(PromoCreate.code)


@dp.callback_query(F.data.startswith("promo_delete_"))
async def callback_promo_delete(callback: CallbackQuery):
    """Удалить промокод"""
    promo_id = int(callback.data.split("_")[2])
    
    try:
        db.delete_promocode(promo_id)
        await callback.answer("✅ Промокод удалён", show_alert=True)
        await show_promos(callback.message, edit=True)
    except Exception as e:
        logger.error(f"Error deleting promo: {e}")
        await callback.answer("❌ Ошибка удаления", show_alert=True)


@dp.callback_query(F.data.startswith("promo_stats_"))
async def callback_promo_stats(callback: CallbackQuery):
    """Статистика промокода"""
    promo_id = int(callback.data.split("_")[2])
    await callback.answer()
    await show_promo_stats(callback.message, promo_id)


# ========== Callback handlers - Рассылка ==========

@dp.callback_query(F.data == "broadcast")
async def callback_broadcast(callback: CallbackQuery, state: FSMContext):
    """Начать рассылку"""
    await callback.answer()
    await callback.message.answer(
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Введите текст сообщения для отправки всем пользователям:\n\n"
        "⚠️ Сообщение будет отправлено ВСЕМ зарегистрированным пользователям!",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(BroadcastMessage.text)


# ========== FSM Handlers - Создание промокода ==========

@dp.message(PromoCreate.code)
async def process_promo_code(message: Message, state: FSMContext):
    """Обработка кода промокода"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    code = message.text.strip().upper()
    
    if len(code) < 3 or len(code) > 20:
        await message.answer("❌ Код должен быть от 3 до 20 символов")
        return
    
    # Проверить существование
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM promocodes WHERE code = ?", (code,))
    exists = cursor.fetchone()
    conn.close()
    
    if exists:
        await message.answer("❌ Такой промокод уже существует")
        return
    
    await state.update_data(code=code)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Рубли", callback_data="promo_type_rub"),
            InlineKeyboardButton(text="% Процент", callback_data="promo_type_percent")
        ],
        [
            InlineKeyboardButton(text="🎁 Баланс", callback_data="promo_type_balance")
        ],
        [
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")
        ]
    ])
    
    await message.answer(
        f"✅ Код: <code>{code}</code>\n\n"
        "Выберите тип скидки:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(PromoCreate.type)


@dp.callback_query(PromoCreate.type, F.data.startswith("promo_type_"))
async def process_promo_type(callback: CallbackQuery, state: FSMContext):
    """Обработка типа промокода"""
    promo_type = callback.data.replace("promo_type_", "")
    await state.update_data(type=promo_type)
    
    type_labels = {
        'rub': 'рублей',
        'percent': 'процентов',
        'balance': 'рублей на баланс'
    }
    
    await callback.message.edit_text(
        f"Введите значение ({type_labels[promo_type]}):",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()
    await state.set_state(PromoCreate.value)


@dp.message(PromoCreate.value)
async def process_promo_value(message: Message, state: FSMContext):
    """Обработка значения промокода"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        value = float(message.text.strip())
        
        data = await state.get_data()
        promo_type = data['type']
        
        if promo_type == 'percent' and (value <= 0 or value > 100):
            await message.answer("❌ Процент должен быть от 1 до 100")
            return
        
        if value <= 0:
            await message.answer("❌ Значение должно быть положительным")
            return
        
        await state.update_data(value=value)
        
        await message.answer(
            "Введите максимальное количество использований\n"
            "(или -1 для неограниченного):",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(PromoCreate.max_uses)
        
    except ValueError:
        await message.answer("❌ Неверный формат числа")


@dp.message(PromoCreate.max_uses)
async def process_promo_max_uses(message: Message, state: FSMContext):
    """Обработка макс. использований"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        max_uses = int(message.text.strip())
        
        if max_uses < -1 or max_uses == 0:
            await message.answer("❌ Введите положительное число или -1")
            return
        
        await state.update_data(max_uses=max_uses)
        
        # Подтверждение
        data = await state.get_data()
        
        type_labels = {
            'rub': '₽ рублей',
            'percent': '% процентов',
            'balance': '₽ на баланс'
        }
        
        max_uses_text = "∞ неограничено" if max_uses == -1 else f"{max_uses} раз"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать", callback_data="promo_confirm_yes"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")
            ]
        ])
        
        await message.answer(
            "📋 <b>Подтверждение создания промокода:</b>\n\n"
            f"🎟️ Код: <code>{data['code']}</code>\n"
            f"💰 Тип: {data['type']}\n"
            f"💵 Значение: {data['value']}{type_labels[data['type']]}\n"
            f"📊 Использований: {max_uses_text}\n\n"
            "Всё верно?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await state.set_state(PromoCreate.confirm)
        
    except ValueError:
        await message.answer("❌ Неверный формат числа")


@dp.callback_query(PromoCreate.confirm, F.data == "promo_confirm_yes")
async def process_promo_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение создания промокода"""
    data = await state.get_data()
    
    try:
        promo_id = db.create_promocode(
            code=data['code'],
            promo_type=data['type'],
            value=data['value'],
            max_uses=data['max_uses']
        )
        
        await callback.message.edit_text(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"🎟️ Код: <code>{data['code']}</code>\n"
            f"ID: {promo_id}",
            parse_mode="HTML"
        )
        await callback.answer("✅ Промокод создан!", show_alert=True)
        
        await state.clear()
        
        # Показать меню через 2 секунды
        await asyncio.sleep(2)
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error creating promo: {e}")
        await callback.message.edit_text("❌ Ошибка создания промокода")
        await callback.answer("❌ Ошибка", show_alert=True)
        await state.clear()


# ========== FSM Handlers - Управление клиентом ==========

@dp.message(ClientManage.value)
async def process_client_value(message: Message, state: FSMContext):
    """Обработка значения для клиента"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    telegram_id = data['telegram_id']
    action = data['action']
    
    try:
        value = float(message.text.strip())
        
        if action == 'balance':
            # Обновить баланс
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET balance = balance + ? 
                WHERE telegram_id = ?
            """, (value, telegram_id))
            conn.commit()
            conn.close()
            
            operation = "начислено" if value > 0 else "списано"
            await message.answer(
                f"✅ Клиенту {telegram_id} {operation} {abs(value)}₽",
                reply_markup=get_main_keyboard()
            )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат числа")
    except Exception as e:
        logger.error(f"Error updating client: {e}")
        await message.answer("❌ Ошибка обновления")
        await state.clear()


# ========== FSM Handlers - Рассылка ==========

@dp.message(BroadcastMessage.text)
async def process_broadcast_text(message: Message, state: FSMContext):
    """Обработка текста рассылки"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    text = message.text.strip()
    
    if len(text) < 1:
        await message.answer("❌ Текст не может быть пустым")
        return
    
    await state.update_data(text=text)
    
    # Получить количество пользователей
    users = db.get_all_users()
    user_count = len(users)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm_yes"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")
        ]
    ])
    
    await message.answer(
        f"📢 <b>Подтверждение рассылки</b>\n\n"
        f"👥 Получателей: {user_count}\n\n"
        f"Текст сообщения:\n{text}\n\n"
        "Отправить?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await state.set_state(BroadcastMessage.confirm)


@dp.callback_query(BroadcastMessage.confirm, F.data == "broadcast_confirm_yes")
async def process_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение рассылки"""
    data = await state.get_data()
    text = data['text']
    
    await callback.message.edit_text("⏳ Отправка сообщений через клиентский бот...")
    await callback.answer()
    
    users = db.get_all_users()
    success = 0
    failed = 0
    
    # Отправляем через КЛИЕНТСКИЙ бот, а не админский
    for user in users:
        try:
            await client_bot.send_message(
                user['telegram_id'],
                f"📢 <b>Сообщение от администрации:</b>\n\n{text}",
                parse_mode="HTML"
            )
            success += 1
            await asyncio.sleep(0.05)  # Чтобы не превысить лимиты Telegram
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {user['telegram_id']}: {e}")
    
    await callback.message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"✅ Отправлено: {success}\n"
        f"❌ Ошибок: {failed}\n\n"
        f"💡 Сообщения пришли клиентам в их основной бот",
        parse_mode="HTML"
    )
    
    await state.clear()
    
    await asyncio.sleep(2)
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )


# ========== Функции отображения - Статистика ==========

async def show_stats(message: Message, edit: bool = False):
    """Показать базовую статистику"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Все заказы
        cursor.execute("SELECT * FROM orders")
        all_orders = cursor.fetchall()
        
        # Completed заказы
        completed_orders = [o for o in all_orders if o['status'] == 'completed']
        
        # Заказы за сегодня
        today = datetime.now().date()
        today_orders = [o for o in all_orders if datetime.fromisoformat(o['created_at']).date() == today]
        
        # Выручка
        total_revenue = sum(o['total_amount'] or 0 for o in completed_orders)
        today_revenue = sum(o['total_amount'] or 0 for o in today_orders if o['status'] == 'completed')
        
        # Средний чек
        avg_check = int(total_revenue / len(completed_orders)) if completed_orders else 0
        
        # Клиенты
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_clients = cursor.fetchone()['count']
        
        # Новые клиенты сегодня
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM users 
            WHERE DATE(created_at) = ?
        """, (today.isoformat(),))
        new_clients_today = cursor.fetchone()['count']
        
        conn.close()
        
        text = (
            "📊 <b>Статистика HotSpot</b>\n\n"
            f"💰 <b>Выручка:</b> {total_revenue:,.0f}₽\n"
            f"📅 <b>За сегодня:</b> {today_revenue:,.0f}₽\n\n"
            f"✅ <b>Выполнено:</b> {len(completed_orders)}\n"
            f"⏳ <b>Ожидают:</b> {len([o for o in all_orders if o['status'] == 'pending'])}\n"
            f"📦 <b>Сегодня:</b> {len(today_orders)} заказов\n\n"
            f"👥 <b>Всего клиентов:</b> {total_clients}\n"
            f"🆕 <b>Новых сегодня:</b> {new_clients_today}\n\n"
            f"📊 <b>Средний чек:</b> {avg_check:,.0f}₽"
        )
        
        if edit:
            await message.edit_text(text, reply_markup=get_main_keyboard(), parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing stats: {e}")
        await message.answer("❌ Ошибка при загрузке статистики")


async def show_detailed_stats(message: Message):
    """Показать детальную статистику"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Периоды
        now = datetime.now()
        today = now.date()
        week_ago = (now - timedelta(days=7)).date()
        month_ago = (now - timedelta(days=30)).date()
        
        # Заказы по периодам
        cursor.execute("SELECT * FROM orders")
        all_orders = cursor.fetchall()
        
        completed = [o for o in all_orders if o['status'] == 'completed']
        today_orders = [o for o in all_orders if datetime.fromisoformat(o['created_at']).date() == today]
        week_orders = [o for o in all_orders if datetime.fromisoformat(o['created_at']).date() >= week_ago]
        month_orders = [o for o in all_orders if datetime.fromisoformat(o['created_at']).date() >= month_ago]
        
        # Выручка
        total_revenue = sum(o['total_amount'] or 0 for o in completed)
        today_revenue = sum(o['total_amount'] or 0 for o in today_orders if o['status'] == 'completed')
        week_revenue = sum(o['total_amount'] or 0 for o in week_orders if o['status'] == 'completed')
        month_revenue = sum(o['total_amount'] or 0 for o in month_orders if o['status'] == 'completed')
        
        # Средние чеки
        avg_total = int(total_revenue / len(completed)) if completed else 0
        avg_week = int(week_revenue / len([o for o in week_orders if o['status'] == 'completed'])) if week_orders else 0
        
        # Статусы
        pending_count = len([o for o in all_orders if o['status'] == 'pending'])
        confirmed_count = len([o for o in all_orders if o['status'] == 'confirmed'])
        cancelled_count = len([o for o in all_orders if o['status'] == 'cancelled'])
        
        # Клиенты
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count']
        
        # Активные клиенты (сделали хотя бы 1 заказ)
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as count 
            FROM orders 
            WHERE status = 'completed'
        """)
        active_users = cursor.fetchone()['count']
        
        # Топ товары
        cursor.execute("""
            SELECT items FROM orders WHERE status = 'completed'
        """)
        orders_data = cursor.fetchall()
        
        product_sales = {}
        for order in orders_data:
            try:
                items = json.loads(order['items']) if isinstance(order['items'], str) else order['items']
                for item in items:
                    name = item.get('name', 'Неизвестно')
                    qty = item.get('quantity', 1)
                    product_sales[name] = product_sales.get(name, 0) + qty
            except:
                pass
        
        top_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:5]
        
        conn.close()
        
        text = (
            "📈 <b>Детальная статистика</b>\n\n"
            "💰 <b>Выручка:</b>\n"
            f"├ Всего: {total_revenue:,.0f}₽\n"
            f"├ За месяц: {month_revenue:,.0f}₽\n"
            f"├ За неделю: {week_revenue:,.0f}₽\n"
            f"└ Сегодня: {today_revenue:,.0f}₽\n\n"
            
            "📦 <b>Заказы:</b>\n"
            f"├ Всего: {len(all_orders)}\n"
            f"├ Выполнено: {len(completed)}\n"
            f"├ Ожидают: {pending_count}\n"
            f"├ Подтверждены: {confirmed_count}\n"
            f"└ Отменены: {cancelled_count}\n\n"
            
            "👥 <b>Клиенты:</b>\n"
            f"├ Всего: {total_users}\n"
            f"├ Активных: {active_users}\n"
            f"└ Конверсия: {int(active_users/total_users*100) if total_users else 0}%\n\n"
            
            "📊 <b>Средний чек:</b>\n"
            f"├ Общий: {avg_total:,.0f}₽\n"
            f"└ За неделю: {avg_week:,.0f}₽\n\n"
            
            "🔥 <b>Топ товары:</b>\n"
        )
        
        for i, (product, sales) in enumerate(top_products, 1):
            text += f"{i}. {product[:30]} - {sales} шт\n"
        
        await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing detailed stats: {e}")
        await message.answer("❌ Ошибка при загрузке статистики")


# ========== Функции отображения - Заказы ==========

async def show_orders(message: Message, edit: bool = False):
    """Показать последние заказы"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 10")
        orders = cursor.fetchall()
        conn.close()
        
        if not orders:
            text = "📦 Заказов пока нет"
            keyboard = get_main_keyboard()
        else:
            text = "📦 <b>Последние 10 заказов:</b>\n\n"
            
            for order in orders:
                status_emoji = {
                    'pending': '⏳',
                    'confirmed': '✅',
                    'completed': '🎉',
                    'cancelled': '❌'
                }.get(order['status'], '❓')
                
                delivery_type = '📍' if order['delivery_type'] == 'pickup' else '🚗'
                
                text += (
                    f"{status_emoji} <b>#{order['id']}</b> {escape_html(order['customer_name']) or 'N/A'} "
                    f"{delivery_type} {order['total_amount'] or 0:,.0f}₽\n"
                )
            
            text += "\n💡 Нажмите на заказ для управления или используйте фильтры"
            keyboard = get_orders_list_keyboard(orders)
        
        if edit:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing orders: {e}")
        await message.answer("❌ Ошибка при загрузке заказов")


async def show_orders_filtered(message: Message, filter_type: str):
    """Показать отфильтрованные заказы"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now()
        today = now.date()
        week_ago = (now - timedelta(days=7)).date()
        
        if filter_type == 'today':
            cursor.execute("""
                SELECT * FROM orders 
                WHERE DATE(created_at) = ? 
                ORDER BY created_at DESC
            """, (today.isoformat(),))
            title = "📅 Заказы за сегодня"
        elif filter_type == 'week':
            cursor.execute("""
                SELECT * FROM orders 
                WHERE DATE(created_at) >= ? 
                ORDER BY created_at DESC
            """, (week_ago.isoformat(),))
            title = "📆 Заказы за неделю"
        else:
            cursor.execute("""
                SELECT * FROM orders 
                WHERE status = ? 
                ORDER BY created_at DESC 
                LIMIT 20
            """, (filter_type,))
            status_names = {
                'pending': 'ожидающие',
                'confirmed': 'подтверждённые',
                'completed': 'завершённые',
                'cancelled': 'отменённые'
            }
            title = f"Заказы: {status_names.get(filter_type, filter_type)}"
        
        orders = cursor.fetchall()
        conn.close()
        
        if not orders:
            text = f"{title}\n\nЗаказов не найдено"
            keyboard = get_orders_filter_keyboard()
        else:
            text = f"<b>{title}</b>\n\n"
            
            for order in orders[:15]:
                status_emoji = {
                    'pending': '⏳',
                    'confirmed': '✅',
                    'completed': '🎉',
                    'cancelled': '❌'
                }.get(order['status'], '❓')
                
                text += (
                    f"{status_emoji} <b>#{order['id']}</b> {escape_html(order['customer_name']) or 'N/A'} "
                    f"- {order['total_amount'] or 0:,.0f}₽\n"
                )
            
            if len(orders) > 15:
                text += f"\n... и ещё {len(orders) - 15}"
            
            text += "\n\n💡 Нажмите на заказ для управления"
            keyboard = get_orders_list_keyboard(orders[:15])
        
        await message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error showing filtered orders: {e}")
        await message.answer("❌ Ошибка при загрузке заказов")


async def show_order_detail(message: Message, order_id: int, edit: bool = False):
    """Показать детали заказа"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        
        if not row:
            await message.answer(f"❌ Заказ #{order_id} не найден")
            return
        
        # Конвертируем Row в dict
        order = dict(row)
        
        # Парсим товары
        items = []
        try:
            items = json.loads(order['items']) if isinstance(order['items'], str) else order['items']
        except:
            pass
        
        # Формируем текст
        status_names = {
            'pending': '⏳ В ожидании',
            'confirmed': '✅ Подтверждён',
            'completed': '🎉 Завершён',
            'cancelled': '❌ Отменён'
        }
        
        payment_names = {
            'sbp_online': '💳 СБП онлайн',
            'sbp_pickup': '💳 СБП при получении',
            'cash': '💵 Наличные',
            'balance': '💰 Баланс'
        }
        
        delivery_info = '📍 Самовывоз' if order['delivery_type'] == 'pickup' else '🚗 Доставка'
        if order['delivery_type'] == 'pickup':
            delivery_info += f": {escape_html(order['pickup_location']) or 'Не указан'}"
        else:
            delivery_info += f": {escape_html(order['delivery_address']) or 'Не указан'}"
        
        text = f"📦 <b>Заказ #{order['id']}</b>\n\n"
        text += f"<b>Статус:</b> {status_names.get(order['status'], order['status'])}\n"
        text += f"<b>Дата:</b> {datetime.fromisoformat(order['created_at']).strftime('%d.%m.%Y %H:%M')}\n\n"
        
        text += f"👤 <b>Клиент:</b> {escape_html(order['customer_name']) or 'Не указан'}\n"
        text += f"📱 <b>Телефон:</b> {escape_html(order['customer_phone']) or 'Не указан'}\n\n"
        
        text += f"{delivery_info}\n"
        text += f"<b>Оплата:</b> {payment_names.get(order['payment_method'], order['payment_method'])}\n\n"
        
        # Подтверждение оплаты СБП
        if order['payment_screenshot']:
            text += f"💳 <b>Подтверждение оплаты:</b>\n"
            text += f"📱 Телефон: {order['payment_phone'] or 'Не указан'}\n"
            if order['payment_confirmed']:
                text += "✅ Оплата подтверждена\n\n"
            else:
                text += "⏳ Ожидает подтверждения\n\n"
        
        # Товары
        text += "🛍️ <b>Товары:</b>\n"
        for item in items:
            text += f"• {escape_html(item.get('name', 'Товар'))}"
            if item.get('flavor'):
                text += f" ({escape_html(item['flavor'])})"
            text += f" - {item.get('quantity', 1)} × {item.get('price', 0)}₽ = {item.get('quantity', 1) * item.get('price', 0)}₽\n"
        
        # Рассчитываем subtotal из items
        subtotal = sum(item.get('quantity', 1) * item.get('price', 0) for item in items)
        
        # Рассчитываем чистую прибыль
        total_cost = 0
        for item in items:
            product_id = item.get('product_id')
            if product_id:
                cursor.execute('SELECT cost_price FROM products WHERE id = ?', (product_id,))
                product = cursor.fetchone()
                cost_price = product['cost_price'] if product and product['cost_price'] else 0
                total_cost += cost_price * item.get('quantity', 1)
        
        gross_profit = subtotal - total_cost  # Валовая прибыль
        discount_spent = (order.get('discount', 0) or 0) + (order.get('balance_used', 0) or 0)
        net_profit = gross_profit - discount_spent  # Чистая прибыль
        
        # Детальный чек
        text += "\n💵 <b>Чек:</b>\n"
        text += f"  📦 Товары: {subtotal:,.0f}₽\n"
        
        if order.get('delivery_cost') and order['delivery_cost'] > 0:
            text += f"  🚗 Доставка: +{order['delivery_cost']:,.0f}₽\n"
        
        if order.get('discount') and order['discount'] > 0:
            text += f"  🏷️ Скидка: -{order['discount']:,.0f}₽\n"
        
        if order.get('balance_used') and order['balance_used'] > 0:
            text += f"  💰 Оплачено балансом: -{order['balance_used']:,.0f}₽\n"
        
        text += f"  ━━━━━━━━━━━━━\n"
        text += f"  💳 <b>К оплате: {order.get('total', 0):,.0f}₽</b>"
        
        if order['cashback_earned'] and order['cashback_earned'] > 0:
            text += f"\n  💚 Кешбэк клиенту: +{order['cashback_earned']:,.0f}₽"
        
        # Добавляем чистую прибыль
        profit_icon = "💚" if net_profit > 0 else ("🟡" if net_profit == 0 else "🔴")
        text += f"\n\n  {profit_icon} <b>Чистая прибыль: {net_profit:,.0f}₽</b>"
        
        # Клавиатура с кнопками
        keyboard = get_order_keyboard(
            order['id'],
            order['status'],
            has_screenshot=bool(order['payment_screenshot']),
            payment_confirmed=bool(order['payment_confirmed'])
        )
        
        if edit:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error showing order detail: {e}")
        await message.answer("❌ Ошибка при загрузке заказа")


# ========== Функции отображения - Клиенты ==========

async def show_clients_menu(message: Message):
    """Показать меню клиентов"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as count 
            FROM orders 
            WHERE status = 'completed'
        """)
        active = cursor.fetchone()['count']
        
        conn.close()
        
        text = (
            "👥 <b>Управление клиентами</b>\n\n"
            f"Всего клиентов: {total}\n"
            f"Активных: {active}\n\n"
            "Выберите действие:"
        )
        
        await message.edit_text(
            text,
            reply_markup=get_clients_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error showing clients menu: {e}")
        await message.answer("❌ Ошибка")


async def show_clients_top(message: Message):
    """Топ клиенты"""
    try:
        users = db.get_all_users()
        users.sort(key=lambda x: x.get('orderCount', 0), reverse=True)
        top_users = users[:10]
        
        if not top_users:
            text = "👥 Клиентов пока нет"
        else:
            text = "🏆 <b>Топ 10 клиентов по заказам:</b>\n\n"
            
            for i, user in enumerate(top_users, 1):
                name = user.get('first_name') or user.get('username') or f"ID {user.get('telegram_id')}"
                name = escape_html(str(name))  # Экранируем HTML
                orders = user.get('orderCount', 0)
                balance = user.get('balance', 0)
                
                text += f"{i}. {name}\n"
                text += f"   📦 {orders} заказов | 💰 {balance:,.0f}₽\n\n"
        
        await message.edit_text(
            text,
            reply_markup=get_clients_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error showing top clients: {e}")
        await message.answer("❌ Ошибка")


async def show_clients_new(message: Message):
    """Новые клиенты"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM users 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        users = [dict(row) for row in cursor.fetchall()]  # Конвертируем в dict
        conn.close()
        
        if not users:
            text = "👥 Новых клиентов нет"
        else:
            text = "🆕 <b>Последние 10 новых клиентов:</b>\n\n"
            
            for user in users:
                name = user.get('first_name') or user.get('username') or f"ID {user.get('telegram_id')}"
                name = escape_html(str(name))  # Экранируем HTML
                date = datetime.fromisoformat(user['created_at']).strftime('%d.%m %H:%M')
                
                text += f"• {name}\n"
                text += f"  📅 {date}\n\n"
        
        await message.edit_text(
            text,
            reply_markup=get_clients_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error showing new clients: {e}")
        await message.answer("❌ Ошибка")


async def show_clients_by_balance(message: Message):
    """Клиенты по балансу"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM users 
            WHERE balance > 0 
            ORDER BY balance DESC 
            LIMIT 15
        """)
        users = [dict(row) for row in cursor.fetchall()]  # Конвертируем в dict
        conn.close()
        
        if not users:
            text = "💰 Нет клиентов с балансом"
        else:
            text = "💰 <b>Клиенты с балансом:</b>\n\n"
            
            for i, user in enumerate(users, 1):
                name = user.get('first_name') or user.get('username') or f"ID {user.get('telegram_id')}"
                name = escape_html(str(name))  # Экранируем HTML
                balance = user.get('balance', 0)
                
                text += f"{i}. {name} - {balance:,.0f}₽\n"
        
        await message.edit_text(
            text,
            reply_markup=get_clients_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error showing clients by balance: {e}")
        await message.answer("❌ Ошибка")


async def show_clients_by_orders(message: Message):
    """Клиенты по количеству заказов"""
    try:
        users = db.get_all_users()
        users.sort(key=lambda x: x.get('orderCount', 0), reverse=True)
        top_users = users[:15]
        
        if not top_users:
            text = "📦 Нет клиентов с заказами"
        else:
            text = "📦 <b>Клиенты по заказам:</b>\n\n"
            
            for i, user in enumerate(top_users, 1):
                name = user.get('first_name') or user.get('username') or f"ID {user.get('telegram_id')}"
                name = escape_html(str(name))  # Экранируем HTML
                orders = user.get('orderCount', 0)
                
                if orders > 0:
                    text += f"{i}. {name} - {orders} заказов\n"
        
        await message.edit_text(
            text,
            reply_markup=get_clients_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error showing clients by orders: {e}")
        await message.answer("❌ Ошибка")


async def show_client_detail(message: Message, telegram_id: int, edit: bool = False):
    """Показать детали клиента"""
    try:
        user = db.get_user(telegram_id)
        
        if not user:
            await message.answer(f"❌ Клиент {telegram_id} не найден")
            return
        
        # Статистика заказов
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                   SUM(CASE WHEN status = 'completed' THEN total_amount ELSE 0 END) as revenue
            FROM orders
            WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?)
        """, (telegram_id,))
        stats = cursor.fetchone()
        conn.close()
        
        name = user.get('first_name') or user.get('username') or f"ID {telegram_id}"
        username = f"@{user.get('username')}" if user.get('username') else "Нет username"
        
        text = (
            f"👤 <b>Клиент: {name}</b>\n\n"
            f"📱 Telegram ID: <code>{telegram_id}</code>\n"
            f"👤 Username: {username}\n"
            f"📱 Телефон: {user.get('phone') or 'Не указан'}\n"
            f"💰 Баланс: {user.get('balance', 0):,.0f}₽\n\n"
            
            f"📊 <b>Статистика:</b>\n"
            f"📦 Всего заказов: {stats['total'] or 0}\n"
            f"✅ Выполнено: {stats['completed'] or 0}\n"
            f"💰 Выручка: {stats['revenue'] or 0:,.0f}₽\n\n"
            
            f"📅 Регистрация: {datetime.fromisoformat(user['created_at']).strftime('%d.%m.%Y')}"
        )
        
        keyboard = get_client_actions_keyboard(telegram_id)
        
        if edit:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing client detail: {e}")
        await message.answer("❌ Ошибка")


async def show_client_orders(message: Message, telegram_id: int):
    """Показать заказы клиента"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.* 
            FROM orders o
            JOIN users u ON o.user_id = u.id
            WHERE u.telegram_id = ?
            ORDER BY o.created_at DESC
            LIMIT 10
        """, (telegram_id,))
        orders = cursor.fetchall()
        conn.close()
        
        if not orders:
            text = f"📦 У клиента {telegram_id} нет заказов"
        else:
            text = f"📦 <b>Заказы клиента {telegram_id}:</b>\n\n"
            
            for order in orders:
                status_emoji = {
                    'pending': '⏳',
                    'confirmed': '✅',
                    'completed': '🎉',
                    'cancelled': '❌'
                }.get(order['status'], '❓')
                
                text += (
                    f"{status_emoji} <b>#{order['id']}</b> - "
                    f"{order['total_amount'] or 0:,.0f}₽\n"
                    f"   {datetime.fromisoformat(order['created_at']).strftime('%d.%m.%Y %H:%M')}\n\n"
                )
        
        await message.answer(
            text,
            reply_markup=get_client_actions_keyboard(telegram_id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error showing client orders: {e}")
        await message.answer("❌ Ошибка")


async def show_client_stats(message: Message, telegram_id: int):
    """Показать статистику клиента"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Детальная статистика
        cursor.execute("""
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                SUM(CASE WHEN status = 'completed' THEN total_amount ELSE 0 END) as revenue,
                AVG(CASE WHEN status = 'completed' THEN total_amount ELSE NULL END) as avg_check,
                MAX(created_at) as last_order
            FROM orders
            WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?)
        """, (telegram_id,))
        stats = cursor.fetchone()
        
        # Любимые товары
        cursor.execute("""
            SELECT items FROM orders 
            WHERE user_id = (SELECT id FROM users WHERE telegram_id = ?)
            AND status = 'completed'
        """, (telegram_id,))
        orders_data = cursor.fetchall()
        
        conn.close()
        
        # Анализ товаров
        product_counts = {}
        for order in orders_data:
            try:
                items = json.loads(order['items']) if isinstance(order['items'], str) else order['items']
                for item in items:
                    name = item.get('name', 'Неизвестно')
                    product_counts[name] = product_counts.get(name, 0) + item.get('quantity', 1)
            except:
                pass
        
        top_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        last_order_text = "Нет"
        if stats['last_order']:
            last_order_text = datetime.fromisoformat(stats['last_order']).strftime('%d.%m.%Y')
        
        text = (
            f"📊 <b>Статистика клиента {telegram_id}</b>\n\n"
            
            f"📦 <b>Заказы:</b>\n"
            f"├ Всего: {stats['total_orders'] or 0}\n"
            f"├ Выполнено: {stats['completed'] or 0}\n"
            f"└ Отменено: {stats['cancelled'] or 0}\n\n"
            
            f"💰 <b>Выручка:</b> {stats['revenue'] or 0:,.0f}₽\n"
            f"📊 <b>Средний чек:</b> {int(stats['avg_check'] or 0):,.0f}₽\n"
            f"📅 <b>Последний заказ:</b> {last_order_text}\n\n"
            
            f"🔥 <b>Любимые товары:</b>\n"
        )
        
        for i, (product, count) in enumerate(top_products, 1):
            text += f"{i}. {product[:25]} - {count} шт\n"
        
        await message.answer(
            text,
            reply_markup=get_client_actions_keyboard(telegram_id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error showing client stats: {e}")
        await message.answer("❌ Ошибка")


# ========== Функции отображения - Промокоды ==========

async def show_promos(message: Message, edit: bool = False):
    """Показать активные промокоды"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM promocodes ORDER BY created_at DESC LIMIT 15")
        promos = cursor.fetchall()
        conn.close()
        
        if not promos:
            text = "🎟️ Активных промокодов нет\n\n💡 Создайте новый промокод"
            keyboard = get_main_keyboard()
        else:
            text = "🎟️ <b>Активные промокоды:</b>\n\n"
            
            for promo in promos:
                type_label = {
                    'percent': '%',
                    'rub': '₽',
                    'balance': '₽ на баланс'
                }.get(promo['type'], '')
                
                uses = f"{promo['current_uses']}/{promo['max_uses'] if promo['max_uses'] != -1 else '∞'}"
                
                text += (
                    f"<code>{promo['code']}</code>\n"
                    f"💰 {promo['value']}{type_label} | 📊 {uses}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                )
            
            keyboard = get_main_keyboard()
        
        if edit:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error showing promos: {e}")
        await message.answer("❌ Ошибка при загрузке промокодов")


async def show_promo_stats(message: Message, promo_id: int):
    """Статистика промокода"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM promocodes WHERE id = ?", (promo_id,))
        promo = cursor.fetchone()
        
        if not promo:
            await message.answer("❌ Промокод не найден")
            return
        
        # Статистика использований
        cursor.execute("""
            SELECT COUNT(*) as count, SUM(o.total_amount) as revenue
            FROM orders o
            WHERE o.promocode = ?
        """, (promo['code'],))
        stats = cursor.fetchone()
        
        conn.close()
        
        type_label = {
            'percent': '%',
            'rub': '₽',
            'balance': '₽ на баланс'
        }.get(promo['type'], '')
        
        text = (
            f"📊 <b>Статистика промокода</b>\n\n"
            f"🎟️ Код: <code>{promo['code']}</code>\n"
            f"💰 Значение: {promo['value']}{type_label}\n\n"
            
            f"📈 <b>Использование:</b>\n"
            f"├ Применений: {stats['count'] or 0}\n"
            f"├ Лимит: {promo['max_uses'] if promo['max_uses'] != -1 else '∞'}\n"
            f"└ Выручка: {stats['revenue'] or 0:,.0f}₽\n\n"
            
            f"📅 Создан: {datetime.fromisoformat(promo['created_at']).strftime('%d.%m.%Y %H:%M')}"
        )
        
        await message.answer(
            text,
            reply_markup=get_promo_keyboard(promo_id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error showing promo stats: {e}")
        await message.answer("❌ Ошибка")


# ========== Уведомления о новых заказах ==========

async def check_new_orders():
    """Проверка новых заказов каждые 30 секунд"""
    global last_checked_order_id
    
    while True:
        try:
            await asyncio.sleep(30)
            
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE id > ? ORDER BY id ASC",
                (last_checked_order_id,)
            )
            new_orders = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            for order in new_orders:
                last_checked_order_id = order['id']
                
                for admin_id in ADMIN_IDS:
                    try:
                        items = []
                        try:
                            items = json.loads(order['items']) if order['items'] else []
                        except:
                            pass
                        
                        items_text = "\n".join([
                            f"  • {escape_html(item['name'])} ({escape_html(item.get('flavor', 'N/A'))}) - {item['quantity']} × {item['price']}₽ = {item['quantity'] * item['price']}₽"
                            for item in items
                        ])
                        
                        # Рассчитываем subtotal из items
                        subtotal = sum(item['quantity'] * item['price'] for item in items)
                        
                        # Рассчитываем чистую прибыль
                        total_cost = 0
                        for item in items:
                            product_id = item.get('product_id')
                            if product_id:
                                conn_profit = db.get_connection()
                                cursor_profit = conn_profit.cursor()
                                cursor_profit.execute('SELECT cost_price FROM products WHERE id = ?', (product_id,))
                                product = cursor_profit.fetchone()
                                cost_price = product['cost_price'] if product and product['cost_price'] else 0
                                conn_profit.close()
                                total_cost += cost_price * item['quantity']
                        
                        gross_profit = subtotal - total_cost  # Валовая прибыль
                        discount_spent = (order.get('discount', 0) or 0) + (order.get('balance_used', 0) or 0)
                        net_profit = gross_profit - discount_spent  # Чистая прибыль
                        
                        delivery_info = ""
                        if order['delivery_type'] == 'pickup':
                            delivery_info = f"📍 <b>Самовывоз:</b> {escape_html(order['pickup_location']) or 'Не указан'}"
                        else:
                            delivery_info = f"🚗 <b>Доставка:</b> {escape_html(order['delivery_address']) or 'Не указан'}"
                        
                        # Формируем чек
                        check_lines = [f"  📦 Товары: {subtotal:,.0f}₽"]
                        
                        if order.get('delivery_cost') and order['delivery_cost'] > 0:
                            check_lines.append(f"  🚗 Доставка: +{order['delivery_cost']:,.0f}₽")
                        
                        if order.get('discount') and order['discount'] > 0:
                            check_lines.append(f"  🏷️ Скидка: -{order['discount']:,.0f}₽")
                        
                        if order.get('balance_used') and order['balance_used'] > 0:
                            check_lines.append(f"  💰 Баланс: -{order['balance_used']:,.0f}₽")
                        
                        check_lines.append("  ━━━━━━━━━━━━━")
                        check_lines.append(f"  💳 <b>К оплате: {order.get('total', 0):,.0f}₽</b>")
                        
                        if order.get('cashback_earned') and order['cashback_earned'] > 0:
                            check_lines.append(f"  💚 Кешбэк: +{order['cashback_earned']:,.0f}₽")
                        
                        # Добавляем чистую прибыль
                        profit_icon = "💚" if net_profit > 0 else ("🟡" if net_profit == 0 else "🔴")
                        check_lines.append("")
                        check_lines.append(f"  {profit_icon} <b>Чистая прибыль: {net_profit:,.0f}₽</b>")
                        
                        check_text = "\n".join(check_lines)
                        
                        payment_names = {
                            'sbp_online': '💳 СБП онлайн',
                            'sbp_pickup': '💳 СБП при получении',
                            'cash': '💵 Наличные',
                            'balance': '💰 Баланс'
                        }
                        
                        text = (
                            "🔔 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
                            f"📦 <b>Заказ #{order['id']}</b>\n"
                            f"📅 {datetime.fromisoformat(order['created_at']).strftime('%d.%m.%Y %H:%M')}\n\n"
                            f"👤 <b>Клиент:</b> {escape_html(order['customer_name']) or 'Не указан'}\n"
                            f"📱 <b>Телефон:</b> {escape_html(order['customer_phone']) or 'Не указан'}\n\n"
                            f"🛍️ <b>Товары:</b>\n{items_text or 'Не указаны'}\n\n"
                            f"💵 <b>Чек:</b>\n{check_text}\n\n"
                            f"{delivery_info}\n"
                            f"💳 <b>Способ оплаты:</b> {payment_names.get(order.get('payment_method'), order.get('payment_method', 'Не указан'))}"
                        )
                        
                        await bot.send_message(
                            admin_id,
                            text,
                            reply_markup=get_order_keyboard(order['id'], order['status']),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Error sending notification to admin {admin_id}: {e}")
                        
        except Exception as e:
            logger.error(f"Error checking new orders: {e}")


# ========== Запуск ==========

# ========== УПРАВЛЕНИЕ СКИДКАМИ ==========

@dp.callback_query(F.data == "discounts")
async def show_discounts(callback: CallbackQuery):
    """Показать список скидок"""
    try:
        discounts = db.get_all_discounts()
        
        text = "💸 <b>Управление скидками</b>\n\n"
        
        if not discounts:
            text += "📭 Скидки не созданы\n\n"
            text += "Создайте первую скидку с помощью кнопки ниже"
        else:
            for discount in discounts:
                status_icon = "✅" if discount['active'] else "❌"
                type_name = {
                    'percent': '📊 Процентная',
                    'fixed': '💰 Фиксированная',
                    'category': '📂 На категорию'
                }.get(discount['type'], discount['type'])
                
                text += f"{status_icon} <b>{escape_html(discount['name'])}</b>\n"
                text += f"   Тип: {type_name}\n"
                text += f"   Значение: {discount['value']}{'%' if discount['type'] == 'percent' else '₽'}\n"
                
                if discount.get('target_name'):
                    text += f"   Цель: {escape_html(discount['target_name'])}\n"
                
                if discount.get('min_purchase', 0) > 0:
                    text += f"   Мин. покупка: {discount['min_purchase']}₽\n"
                
                if discount.get('start_date') or discount.get('end_date'):
                    dates = []
                    if discount.get('start_date'):
                        dates.append(f"с {discount['start_date'][:10]}")
                    if discount.get('end_date'):
                        dates.append(f"до {discount['end_date'][:10]}")
                    text += f"   Период: {' '.join(dates)}\n"
                
                text += f"   Приоритет: {discount.get('priority', 0)}\n"
                text += f"   ID: <code>{discount['id']}</code>\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать скидку", callback_data="discount_create")],
            [InlineKeyboardButton(text="« Назад", callback_data="back_to_main")]
        ])
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error showing discounts: {e}", exc_info=True)
        await callback.answer("Ошибка при загрузке скидок", show_alert=True)


@dp.callback_query(F.data == "discount_create")
async def start_discount_creation(callback: CallbackQuery, state: FSMContext):
    """Начать создание скидки"""
    await state.set_state(DiscountCreate.name)
    await callback.message.edit_text(
        "💸 <b>Создание новой скидки</b>\n\n"
        "Введите название скидки:\n"
        "(например: Скидка 15% на все товары)",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(StateFilter(DiscountCreate.name))
async def discount_name_received(message: Message, state: FSMContext):
    """Получено название скидки"""
    await state.update_data(name=message.text)
    await state.set_state(DiscountCreate.type)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Процентная скидка", callback_data="dtype_percent")],
        [InlineKeyboardButton(text="💰 Фиксированная скидка", callback_data="dtype_fixed")],
        [InlineKeyboardButton(text="📂 Скидка на категорию", callback_data="dtype_category")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main")]
    ])
    
    await message.answer(
        "Выберите тип скидки:",
        reply_markup=keyboard
    )


@dp.callback_query(StateFilter(DiscountCreate.type), F.data.startswith("dtype_"))
async def discount_type_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран тип скидки"""
    discount_type = callback.data.split("_")[1]
    await state.update_data(type=discount_type)
    await state.set_state(DiscountCreate.value)
    
    type_hints = {
        'percent': 'Введите процент скидки (например: 15):',
        'fixed': 'Введите сумму скидки в рублях (например: 500):',
        'category': 'Введите процент скидки на категорию (например: 20):'
    }
    
    await callback.message.edit_text(type_hints.get(discount_type, 'Введите значение скидки:'))
    await callback.answer()


@dp.message(StateFilter(DiscountCreate.value))
async def discount_value_received(message: Message, state: FSMContext):
    """Получено значение скидки"""
    try:
        value = float(message.text.replace(',', '.'))
        await state.update_data(value=value)
        
        data = await state.get_data()
        discount_type = data.get('type')
        
        # Если скидка на категорию - запросить ID
        if discount_type == 'category':
            await state.set_state(DiscountCreate.target_id)
            categories = db.get_categories()
            text = "Выберите категорию:\n\n"
            for cat in categories:
                text += f"ID: <code>{cat['id']}</code> - {escape_html(cat['name'])}\n"
            text += "\nВведите ID категории:"
            await message.answer(text, parse_mode="HTML")
        else:
            # Перейти к минимальной сумме покупки
            await state.update_data(target_id=None)
            await state.set_state(DiscountCreate.min_purchase)
            await message.answer(
                "Введите минимальную сумму покупки для применения скидки (в рублях):\n"
                "(введите 0, если ограничения нет)"
            )
    except ValueError:
        await message.answer("❌ Неверный формат! Введите число:")


@dp.message(StateFilter(DiscountCreate.target_id))
async def discount_target_received(message: Message, state: FSMContext):
    """Получен ID цели скидки"""
    try:
        target_id = int(message.text)
        await state.update_data(target_id=target_id)
        await state.set_state(DiscountCreate.min_purchase)
        await message.answer(
            "Введите минимальную сумму покупки для применения скидки (в рублях):\n"
            "(введите 0, если ограничения нет)"
        )
    except ValueError:
        await message.answer("❌ Неверный формат! Введите число (ID):")


@dp.message(StateFilter(DiscountCreate.min_purchase))
async def discount_min_purchase_received(message: Message, state: FSMContext):
    """Получена минимальная сумма покупки"""
    try:
        min_purchase = float(message.text.replace(',', '.'))
        await state.update_data(min_purchase=min_purchase)
        
        # Показать подтверждение
        data = await state.get_data()
        
        type_names = {
            'percent': '📊 Процентная',
            'fixed': '💰 Фиксированная',
            'category': '📂 На категорию',
            'category_fixed': '📂 На категорию (фикс.)',
            'product': '🛍️ На товар'
        }
        
        text = "💸 <b>Подтверждение создания скидки</b>\n\n"
        text += f"<b>Название:</b> {escape_html(data['name'])}\n"
        text += f"<b>Тип:</b> {type_names.get(data['type'], data['type'])}\n"
        text += f"<b>Значение:</b> {data['value']}{'%' if data['type'] == 'percent' else '₽'}\n"
        
        if data.get('target_id'):
            text += f"<b>ID цели:</b> {data['target_id']}\n"
        
        if min_purchase > 0:
            text += f"<b>Мин. покупка:</b> {min_purchase}₽\n"
        
        text += "\nСоздать скидку?"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Создать", callback_data="confirm_discount_create"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_discount_create")
            ]
        ])
        
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    except ValueError:
        await message.answer("❌ Неверный формат! Введите число:")


# Удалён обработчик discount_priority_received - priority больше не используется


@dp.callback_query(F.data == "confirm_discount_create")
async def confirm_discount_creation(callback: CallbackQuery, state: FSMContext):
    """Подтвердить создание скидки"""
    try:
        data = await state.get_data()
        
        discount_id = db.create_discount(
            name=data['name'],
            discount_type=data['type'],
            value=data['value'],
            target_id=data.get('target_id'),
            min_purchase=data.get('min_purchase', 0),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            description=data.get('description'),
            priority=data.get('priority', 0)
        )
        
        await state.clear()
        await callback.message.edit_text(
            f"✅ Скидка создана успешно!\n\n"
            f"ID: <code>{discount_id}</code>\n"
            f"Название: {escape_html(data['name'])}\n\n"
            f"Скидка будет автоматически применяться при оформлении заказов.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        await callback.answer("Скидка создана!")
    except Exception as e:
        logger.error(f"Error creating discount: {e}", exc_info=True)
        await callback.answer("Ошибка при создании скидки", show_alert=True)


@dp.callback_query(F.data == "cancel_discount_create")
async def cancel_discount_creation(callback: CallbackQuery, state: FSMContext):
    """Отменить создание скидки"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Создание скидки отменено",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()


# ========== STARTUP/SHUTDOWN ==========

# ========== Управление наличием ==========

@dp.callback_query(F.data == "stock_manage")
async def stock_manage_start(callback: CallbackQuery, state: FSMContext):
    """Начало управления наличием - выбор бренда"""
    await callback.answer()
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL ORDER BY brand')
    brands = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not brands:
        await callback.message.edit_text(
            "❌ Нет доступных брендов",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
            ])
        )
        return
    
    keyboard = []
    for brand in brands:
        keyboard.append([InlineKeyboardButton(text=brand, callback_data=f"stock_brand_{brand}")])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    
    await callback.message.edit_text(
        "📦 <b>Управление наличием</b>\n\nВыберите бренд:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await state.set_state(StockManage.select_brand)


@dp.callback_query(F.data.startswith("stock_brand_"))
async def stock_select_product(callback: CallbackQuery, state: FSMContext):
    """Выбор товара бренда"""
    await callback.answer()
    
    brand = callback.data.replace("stock_brand_", "")
    await state.update_data(brand=brand)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.name, COUNT(v.id) as variant_count
        FROM products p
        LEFT JOIN product_variants v ON p.id = v.product_id
        WHERE p.brand = ?
        GROUP BY p.id
        ORDER BY p.name
    ''', (brand,))
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not products:
        await callback.message.edit_text(
            f"❌ У бренда <b>{brand}</b> нет товаров",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="stock_manage")]
            ]),
            parse_mode="HTML"
        )
        return
    
    keyboard = []
    for product in products:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{product['name']} ({product['variant_count']} вкусов)",
                callback_data=f"stock_product_{product['id']}"
            )
        ])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="stock_manage")])
    
    await callback.message.edit_text(
        f"📦 <b>Бренд: {brand}</b>\n\nВыберите товар:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await state.set_state(StockManage.select_product)


@dp.callback_query(F.data.startswith("stock_product_"))
async def stock_show_variants(callback: CallbackQuery, state: FSMContext):
    """Показать варианты товара для обновления"""
    await callback.answer()
    
    product_id = int(callback.data.replace("stock_product_", ""))
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, brand FROM products WHERE id = ?', (product_id,))
    product = dict(cursor.fetchone())
    
    cursor.execute('''
        SELECT id, flavor, quantity 
        FROM product_variants 
        WHERE product_id = ? 
        ORDER BY flavor
    ''', (product_id,))
    variants = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    await state.update_data(product_id=product_id, product_name=product['name'], brand=product['brand'])
    
    text = f"📦 <b>{product['brand']} - {product['name']}</b>\n\n<b>Текущее наличие:</b>\n\n"
    
    for i, variant in enumerate(variants, 1):
        status = "✅" if variant['quantity'] > 5 else ("⚠️" if variant['quantity'] > 0 else "❌")
        text += f"{status} {i}. <b>{variant['flavor']}</b>: {variant['quantity']} шт\n"
    
    text += (
        f"\n<i>Чтобы обновить наличие, отправьте данные в формате:</i>\n"
        f"<code>Вкус количество</code> или <code>Вкус: количество</code>\n\n"
        f"<b>Примеры:</b>\n"
        f"<code>Клубника 10\nБанан +5\nЛимон -3</code>\n\n"
        f"Или с двоеточием:\n"
        f"<code>Клубника: 10\nБанан: +5\nЛимон: -3</code>\n\n"
        f"<i>Используйте + для добавления, - для вычитания, или просто число для установки.</i>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить вкус", callback_data=f"stock_add_flavor_{product_id}")],
        [InlineKeyboardButton(text="◀️ Назад к товарам", callback_data=f"stock_brand_{product['brand']}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(StockManage.update_variants)


@dp.message(StockManage.update_variants)
async def stock_update_variants(message: Message, state: FSMContext):
    """Обновить наличие вариантов"""
    data = await state.get_data()
    product_id = data.get('product_id')
    product_name = data.get('product_name')
    
    lines = message.text.strip().split('\n')
    updates = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Поддержка двух форматов:
        # 1. "Вкус: количество" (с двоеточием)
        # 2. "Вкус количество" (без двоеточия)
        if ':' in line:
            parts = line.split(':', 1)
            flavor = parts[0].strip()
            quantity_str = parts[1].strip()
        else:
            # Разделяем по последнему пробелу (число всегда в конце)
            parts = line.rsplit(maxsplit=1)
            if len(parts) != 2:
                continue
            flavor = parts[0].strip()
            quantity_str = parts[1].strip()
        
        if quantity_str.startswith('+'):
            operation = 'add'
            try:
                value = int(quantity_str[1:].strip())
            except ValueError:
                continue
        elif quantity_str.startswith('-'):
            operation = 'subtract'
            try:
                value = int(quantity_str[1:].strip())
            except ValueError:
                continue
        else:
            operation = 'set'
            try:
                value = int(quantity_str.strip())
            except ValueError:
                continue
        
        updates[flavor] = {'operation': operation, 'value': value}
    
    if not updates:
        await message.answer(
            "❌ Не удалось распознать данные. Используйте формат:\n<code>Вкус: количество</code>",
            parse_mode="HTML"
        )
        return
    
    conn = db.get_connection()
    cursor = conn.cursor()
    updated = []
    not_found = []
    
    for flavor, update_data in updates.items():
        cursor.execute('''
            SELECT id, quantity FROM product_variants 
            WHERE product_id = ? AND flavor LIKE ?
        ''', (product_id, f"%{flavor}%"))
        
        variant = cursor.fetchone()
        
        if not variant:
            not_found.append(flavor)
            continue
        
        variant_id = variant[0]
        current_qty = variant[1]
        
        if update_data['operation'] == 'add':
            new_qty = current_qty + update_data['value']
        elif update_data['operation'] == 'subtract':
            new_qty = max(0, current_qty - update_data['value'])
        else:
            new_qty = update_data['value']
        
        cursor.execute('UPDATE product_variants SET quantity = ? WHERE id = ?', (new_qty, variant_id))
        updated.append(f"✅ <b>{flavor}</b>: {current_qty} → {new_qty} шт")
    
    conn.commit()
    conn.close()
    
    response = f"📦 <b>{product_name}</b>\n\n<b>Обновлено:</b>\n" + "\n".join(updated)
    
    if not_found:
        response += f"\n\n<b>Не найдено:</b>\n" + "\n".join(f"❌ {f}" for f in not_found)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu")]
    ])
    
    await message.answer(response, reply_markup=keyboard, parse_mode="HTML")
    await state.clear()


@dp.callback_query(F.data.startswith("stock_add_flavor_"))
async def stock_add_flavor_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление нового вкуса"""
    await callback.answer()
    
    product_id = int(callback.data.replace("stock_add_flavor_", ""))
    
    # Сохраняем product_id в state
    data = await state.get_data()
    await state.update_data(product_id=product_id)
    
    await callback.message.answer(
        "➕ <b>Добавление нового вкуса</b>\n\n"
        "Введите название вкуса:\n"
        "<i>Например: Клубника, Банан</i>",
        parse_mode="HTML"
    )
    await state.set_state(StockManage.add_flavor_name)


@dp.message(StockManage.add_flavor_name)
async def stock_add_flavor_name_received(message: Message, state: FSMContext):
    """Получено название вкуса"""
    flavor_name = message.text.strip()
    
    if not flavor_name:
        await message.answer("❌ Название вкуса не может быть пустым. Попробуйте еще раз:")
        return
    
    await state.update_data(new_flavor_name=flavor_name)
    
    await message.answer(
        f"✅ Вкус: <b>{escape_html(flavor_name)}</b>\n\n"
        f"Теперь введите количество:\n"
        f"<i>Например: 10</i>",
        parse_mode="HTML"
    )
    await state.set_state(StockManage.add_flavor_quantity)


@dp.message(StockManage.add_flavor_quantity)
async def stock_add_flavor_quantity_received(message: Message, state: FSMContext):
    """Получено количество для нового вкуса"""
    try:
        quantity = int(message.text.strip())
        
        if quantity < 0:
            await message.answer("❌ Количество не может быть отрицательным. Попробуйте еще раз:")
            return
        
        data = await state.get_data()
        product_id = data.get('product_id')
        flavor_name = data.get('new_flavor_name')
        
        # Добавляем новый вариант в БД
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже такой вкус
        cursor.execute('''
            SELECT id FROM product_variants 
            WHERE product_id = ? AND flavor = ?
        ''', (product_id, flavor_name))
        
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            await message.answer(
                f"⚠️ Вкус <b>{escape_html(flavor_name)}</b> уже существует!\n\n"
                f"Используйте обновление наличия для изменения количества.",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Добавляем новый вариант
        cursor.execute('''
            INSERT INTO product_variants (product_id, flavor, quantity)
            VALUES (?, ?, ?)
        ''', (product_id, flavor_name, quantity))
        
        conn.commit()
        conn.close()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu")]
        ])
        
        await message.answer(
            f"✅ <b>Вкус успешно добавлен!</b>\n\n"
            f"📦 Вкус: <b>{escape_html(flavor_name)}</b>\n"
            f"📊 Количество: {quantity} шт",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат! Введите целое число:")


async def on_startup():
    """При запуске бота"""
    global last_checked_order_id
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) as max_id FROM orders")
        result = cursor.fetchone()
        last_checked_order_id = result['max_id'] or 0
        conn.close()
        logger.info(f"Last order ID: {last_checked_order_id}")
    except Exception as e:
        logger.error(f"Error getting last order ID: {e}")
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "✅ <b>Admin Bot v3.0 запущен!</b>\n\n"
                "🎉 <b>Новые функции:</b>\n"
                "• 📦 Управление наличием товара через бота\n"
                "• ➕ Добавление новых вкусов\n"
                "• 💰 Отображение чистой прибыли в заказах\n"
                "• 📊 Детальная статистика прибыли\n"
                "• 👥 Управление клиентами (бан, баланс)\n"
                "• 🎲 Случайный выбор клиента для розыгрыша\n"
                "• 🏷️ Управление скидками и промокодами\n"
                "• 📸 Мультифото для товаров\n\n"
                "💡 <i>Используйте /start для открытия меню</i>\n\n"
                "🛠️ <b>Техподдержка:</b> @x32asm",
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")
    
    asyncio.create_task(check_new_orders())


async def on_shutdown():
    """При остановке бота"""
    logger.info("Shutting down admin bot...")
    # Закрыть клиентский бот
    await client_bot.session.close()


async def main():
    """Главная функция"""
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    logger.info("Starting admin bot v2.0...")
    
    try:
        await dp.start_polling(bot)
    finally:
        # Убедиться, что сессии закрыты
        await bot.session.close()
        await client_bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
