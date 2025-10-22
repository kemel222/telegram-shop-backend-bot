"""
API сервер для HotSpot Shop
FastAPI + CORS + статические файлы
"""
from fastapi import FastAPI, HTTPException, Header, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging
from pathlib import Path
import shutil
import uuid
from datetime import datetime

from database import Database
from config import *

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация
app = FastAPI(title="HotSpot Shop API", version="2.0")
db = Database(DATABASE_PATH)

# Создать необходимые директории при старте
@app.on_event("startup")
async def startup_event():
    """Создание необходимых папок при старте сервера"""
    required_dirs = [
        Path("webapp/static/payment_screenshots"),
        Path("webapp/static/images"),
        Path("logs")
    ]
    
    for directory in required_dirs:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Directory ready: {directory}")
    
    logger.info("🚀 Server started successfully!")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы
webapp_path = Path("webapp")
if webapp_path.exists():
    app.mount("/static", StaticFiles(directory="webapp/static"), name="static")


# ========== Pydantic Models ==========

class AddToCartRequest(BaseModel):
    variant_id: int
    quantity: int = 1


class UpdateCartRequest(BaseModel):
    variant_id: int
    quantity: int


class RemoveFromCartRequest(BaseModel):
    variant_id: int


class ToggleFavoriteRequest(BaseModel):
    product_id: int


class ValidatePromoRequest(BaseModel):
    code: str
    expected_type: Optional[str] = None  # 'balance', 'discount', None (любой)


class ApplyPromoRequest(BaseModel):
    code: str


class CreateOrderRequest(BaseModel):
    delivery_type: str  # 'pickup' or 'delivery'
    pickup_location: Optional[str] = None
    delivery_address: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    payment_method: str  # 'sbp_online', 'sbp_pickup', 'cash', 'balance'
    promocode: Optional[str] = None
    use_balance: bool = False


class UpdateOrderStatusRequest(BaseModel):
    status: str


class RegisterUserRequest(BaseModel):
    telegram_user_id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = 'ru'
    is_premium: Optional[bool] = False


# ========== Helper Functions ==========

def get_user_id_from_header(x_telegram_user_id: Optional[str]) -> Optional[int]:
    """Получить user_id из заголовка"""
    if not x_telegram_user_id or x_telegram_user_id in ['null', 'undefined', '']:
        return None
    try:
        return db.get_or_create_user(int(x_telegram_user_id))
    except ValueError:
        return None


def calculate_order_total(cart_items: List[dict], delivery_cost: float, 
                         discount: float, balance_used: float) -> dict:
    """Рассчитать итоговую сумму заказа"""
    subtotal = sum(item['price'] * item['cart_quantity'] for item in cart_items)
    total = subtotal + delivery_cost - discount - balance_used
    total = max(0, total)  # Не может быть отрицательной
    
    # Рассчитать кешбек ТОЛЬКО если есть реальная оплата (не только балансом)
    # Если оплачено полностью балансом (total = 0), кешбек не начисляется
    cashback_earned = 0
    if total > 0:
        for item in cart_items:
            category_id = item.get('category_id', 1)
            cashback_rate = CASHBACK_RATES.get(category_id, 3.0)
            item_cashback = (item['price'] * item['cart_quantity']) * cashback_rate / 100
            cashback_earned += item_cashback
        
        cashback_earned = round(cashback_earned, 2)
    
    return {
        'subtotal': subtotal,
        'delivery_cost': delivery_cost,
        'discount': discount,
        'balance_used': balance_used,
        'total': total,
        'cashback_earned': cashback_earned
    }


# ========== PUBLIC API ENDPOINTS ==========

@app.get("/")
async def read_index(request: Request):
    """Главная страница"""
    # Проверить хост - если это admin.hotspotovich.shop, показать админку
    host = request.headers.get('host', '').lower()
    logger.info(f"Index request from host: {host}, headers: {dict(request.headers)}")
    
    if 'admin.hotspotovich.shop' in host:
        # Для поддомена admin показываем админ-панель
        admin_file = webapp_path / "admin.html"
        logger.info(f"Redirecting to admin panel. File exists: {admin_file.exists()}")
        if admin_file.exists():
            return FileResponse(admin_file)
        raise HTTPException(status_code=404, detail="Admin panel not found")
    
    # Для обычного домена показываем главную страницу
    index_file = webapp_path / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "HotSpot Shop API", "version": "2.0"}


@app.get("/admin")
async def read_admin(request: Request, x_telegram_user_id: Optional[str] = Header(None)):
    """Админ-панель"""
    # Всегда показывать admin.html - проверка будет на клиенте
    admin_file = webapp_path / "admin.html"
    logger.info(f"Admin request from host: {request.headers.get('host', '')}")
    if admin_file.exists():
        return FileResponse(admin_file)
    raise HTTPException(status_code=404, detail="Admin panel not found")


@app.get("/admin_login.html")
async def read_admin_login():
    """Страница входа для админа"""
    login_file = webapp_path / "admin_login.html"
    if login_file.exists():
        return FileResponse(login_file)
    raise HTTPException(status_code=404, detail="Admin login page not found")


@app.post("/api/admin/verify")
async def verify_admin(
    request: Request,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Проверить, является ли пользователь администратором"""
    try:
        telegram_id_str = x_telegram_user_id
        if not telegram_id_str or telegram_id_str in ['null', 'undefined', '']:
            raise HTTPException(status_code=403, detail="Telegram ID not provided")
        
        try:
            telegram_id = int(telegram_id_str)
        except ValueError:
            raise HTTPException(status_code=403, detail="Invalid Telegram ID format")
        
        logger.info(f"Verifying admin access for Telegram ID: {telegram_id}")
        logger.info(f"ADMIN_IDS: {ADMIN_IDS}")
        
        if telegram_id in ADMIN_IDS:
            logger.info(f"Admin verified: {telegram_id}")
            return {"success": True, "message": "Admin verified", "telegram_id": telegram_id}
        else:
            logger.warning(f"Access denied for Telegram ID: {telegram_id}")
            raise HTTPException(status_code=403, detail="Not an admin")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying admin: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/categories")
async def get_categories():
    """Получить все категории"""
    try:
        categories = db.get_categories()
        return {"success": True, "data": categories}
    except Exception as e:
        logger.error(f"Error getting categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/products")
async def get_products(category_id: Optional[int] = None):
    """Получить товары"""
    try:
        products = db.get_products(category_id=category_id)
        
        # Добавить изображения для каждого товара
        for product in products:
            images = db.get_product_images(product['id'])
            product['images'] = images
            # Для обратной совместимости: если есть изображения, первое = image_url
            if images:
                product['image_url'] = images[0]['image_url']
        
        return {"success": True, "data": products}
    except Exception as e:
        logger.error(f"Error getting products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    """Получить товар по ID"""
    try:
        product = db.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"success": True, "data": product}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_products(q: str):
    """Поиск товаров"""
    try:
        if len(q) < 2:
            return {"success": True, "data": []}
        products = db.search_products(q)
        return {"success": True, "data": products}
    except Exception as e:
        logger.error(f"Error searching products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/user")
async def get_user(
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    first_name: Optional[str] = None
):
    """Получить или создать пользователя"""
    try:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")
        
        # Создать или получить пользователя
        internal_user_id = db.get_or_create_user(user_id, username, first_name)
        user = db.get_user(internal_user_id)
        
        return {"success": True, "data": user}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/user/{telegram_user_id}")
async def get_user_by_telegram_id(telegram_user_id: int):
    """Получить пользователя по Telegram ID"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Сначала проверим какие колонки существуют
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cursor.fetchall()}
        
        # Построим SELECT динамически в зависимости от доступных колонок
        base_columns = ['id', 'telegram_id', 'first_name', 'username', 'phone', 'balance', 'created_at', 'updated_at']
        optional_columns = ['last_name', 'language_code', 'is_premium', 'is_banned']
        
        select_columns = base_columns + [col for col in optional_columns if col in columns]
        select_query = f"SELECT {', '.join(select_columns)} FROM users WHERE telegram_id = ?"
        
        cursor.execute(select_query, (telegram_user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Получить избранное (с проверкой структуры таблицы)
        try:
            cursor.execute("PRAGMA table_info(favorites)")
            fav_columns = {row[1] for row in cursor.fetchall()}
            
            # Определить название колонки для product/variant ID
            if 'variant_id' in fav_columns:
                cursor.execute('SELECT variant_id FROM favorites WHERE user_id = ?', (user['id'],))
                favorites = [row['variant_id'] for row in cursor.fetchall()]
            elif 'product_id' in fav_columns:
                cursor.execute('SELECT product_id FROM favorites WHERE user_id = ?', (user['id'],))
                favorites = [row['product_id'] for row in cursor.fetchall()]
            else:
                favorites = []
        except Exception as e:
            logger.warning(f"Could not fetch favorites: {e}")
            favorites = []
        
        return {
            "success": True,
            "user": dict(user),
            "favorites": favorites
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user by telegram_id: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/user/register")
async def register_user(request: RegisterUserRequest):
    """Зарегистрировать нового пользователя"""
    try:
        logger.info(f"Registering new user: {request.telegram_user_id}")
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Проверить существует ли пользователь
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', 
                      (request.telegram_user_id,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            logger.info(f"User already exists: {request.telegram_user_id}, returning existing user data")
            
            # Обновить username если изменился
            cursor.execute('''
                UPDATE users 
                SET username = ?,
                    first_name = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            ''', (request.username, request.first_name, request.telegram_user_id))
            conn.commit()
            
            # Вернуть данные существующего пользователя
            cursor.execute('''
                SELECT id, telegram_id, first_name, username, phone, balance, 
                       created_at, updated_at
                FROM users 
                WHERE telegram_id = ?
            ''', (request.telegram_user_id,))
            user = cursor.fetchone()
            conn.close()
            
            return {
                "success": True,
                "message": "User already registered",
                "user": dict(user)
            }
        
        # Проверим какие колонки существуют
        cursor.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cursor.fetchall()}
        
        # Подготовим данные для вставки
        insert_columns = ['telegram_id', 'first_name', 'username', 'balance', 'created_at', 'updated_at']
        insert_values = [request.telegram_user_id, request.first_name, request.username, 0, 'CURRENT_TIMESTAMP', 'CURRENT_TIMESTAMP']
        
        # Добавим опциональные поля если они существуют
        if 'last_name' in columns:
            insert_columns.insert(2, 'last_name')
            insert_values.insert(2, request.last_name)
        
        if 'language_code' in columns:
            insert_columns.insert(3, 'language_code')
            insert_values.insert(3, request.language_code)
        
        if 'is_premium' in columns:
            insert_columns.insert(4, 'is_premium')
            insert_values.insert(4, request.is_premium)
        
        # Построим INSERT запрос
        placeholders = []
        actual_values = []
        for i, col in enumerate(insert_columns):
            if col in ['created_at', 'updated_at']:
                placeholders.append('CURRENT_TIMESTAMP')
            else:
                placeholders.append('?')
                actual_values.append(insert_values[i])
        
        insert_query = f'''
            INSERT INTO users ({', '.join(insert_columns)})
            VALUES ({', '.join(placeholders)})
        '''
        
        cursor.execute(insert_query, actual_values)
        user_id = cursor.lastrowid
        conn.commit()
        
        # Получить созданного пользователя (используя динамический SELECT)
        base_columns = ['id', 'telegram_id', 'first_name', 'username', 'phone', 'balance', 'created_at', 'updated_at']
        optional_columns = ['last_name', 'language_code', 'is_premium']
        select_columns = base_columns + [col for col in optional_columns if col in columns]
        select_query = f"SELECT {', '.join(select_columns)} FROM users WHERE id = ?"
        
        cursor.execute(select_query, (user_id,))
        user = cursor.fetchone()
        
        logger.info(f"User registered successfully: {request.telegram_user_id} (id: {user_id})")
        
        return {
            "success": True,
            "message": "User registered successfully",
            "user": dict(user)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/user/phone")
async def update_user_phone(
    request: Request,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Обновить телефон пользователя"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        data = await request.json()
        phone = data.get('phone')
        
        if not phone:
            raise HTTPException(status_code=400, detail="Phone required")
        
        db.update_user_info(user_id, phone=phone)
        
        return {"success": True, "message": "Phone updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating phone: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/user/{telegram_user_id}/update-username")
async def update_user_username(
    telegram_user_id: int,
    request: Request,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Обновить username пользователя"""
    try:
        # Проверить что запрос от того же пользователя
        if x_telegram_user_id and int(x_telegram_user_id) != telegram_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        data = await request.json()
        username = data.get('username')
        
        if not username:
            return {"success": True, "message": "No username provided"}
        
        # Получить ID пользователя
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_user_id,))
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Обновить username
        cursor.execute('''
            UPDATE users 
            SET username = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (username, user['id']))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated username for user {telegram_user_id}: {username}")
        
        return {"success": True, "message": "Username updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating username: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== CART ENDPOINTS ==========

@app.get("/api/cart")
async def get_cart(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить корзину с расчетом автоматических скидок"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            return {"success": True, "data": [], "discount_info": None}
        
        cart = db.get_cart(user_id)
        
        # Рассчитать автоматические скидки
        discount_info = None
        if cart:
            # Подготовить данные корзины для расчета скидок
            cart_items_with_details = []
            subtotal = 0
            
            for item in cart:
                item_total = item['price'] * item['cart_quantity']
                subtotal += item_total
                cart_items_with_details.append({
                    'variant_id': item['variant_id'],
                    'product_id': item['product_id'],
                    'category_id': item['category_id'],
                    'price': item['price'],
                    'quantity': item['cart_quantity']
                })
            
            # Получить применимые скидки
            discount_info = db.calculate_discount(cart_items_with_details, subtotal)
        
        return {
            "success": True, 
            "data": cart,
            "discount_info": discount_info
        }
    except Exception as e:
        logger.error(f"Error getting cart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cart/add")
async def add_to_cart(
    request: AddToCartRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Добавить вариант в корзину"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        db.add_to_cart(user_id, request.variant_id, request.quantity)
        return {"success": True, "message": "Added to cart"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to cart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cart/update")
async def update_cart(
    request: UpdateCartRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Обновить количество варианта в корзине"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        db.update_cart_item(user_id, request.variant_id, request.quantity)
        return {"success": True, "message": "Cart updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating cart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cart/remove")
async def remove_from_cart(
    request: RemoveFromCartRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Удалить вариант из корзины"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        db.remove_from_cart(user_id, request.variant_id)
        return {"success": True, "message": "Removed from cart"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing from cart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cart/sync")
async def sync_cart(
    request: Request,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Синхронизировать корзину (полная замена)"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        data = await request.json()
        items = data.get('items', [])
        
        # Очистить текущую корзину
        db.clear_cart(user_id)
        
        # Добавить все товары из запроса
        for item in items:
            variant_id = item.get('variant_id') or item.get('variantId')
            quantity = item.get('quantity', 1)
            if variant_id and quantity > 0:
                db.add_to_cart(user_id, variant_id, quantity)
        
        return {"success": True, "message": "Cart synced"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing cart: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== FAVORITES ENDPOINTS ==========

@app.get("/api/favorites")
async def get_favorites(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить избранное"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            return {"success": True, "data": []}
        
        favorites = db.get_favorites(user_id)
        return {"success": True, "data": favorites}
    except Exception as e:
        logger.error(f"Error getting favorites: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/favorites/toggle")
async def toggle_favorite(
    request: ToggleFavoriteRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Добавить/удалить из избранного"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        added = db.toggle_favorite(user_id, request.product_id)
        message = "Added to favorites" if added else "Removed from favorites"
        return {"success": True, "message": message, "added": added}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== PROMOCODES ENDPOINTS ==========

@app.post("/api/promocode/validate")
async def validate_promo(
    request: ValidatePromoRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Проверить промокод"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        promo = db.get_promocode(request.code)
        if not promo:
            return {"valid": False, "error": "Промокод не найден"}
        
        # Проверить тип промокода если указан expected_type
        if request.expected_type:
            promo_type = promo.get('type', 'percent')
            
            # Для expected_type='discount' принимаем 'percent' и 'rub'
            if request.expected_type == 'discount':
                if promo_type not in ['percent', 'rub']:
                    return {"valid": False, "error": "Промокод не подходит для скидки"}
            # Для expected_type='balance' принимаем только 'balance'
            elif request.expected_type == 'balance':
                if promo_type != 'balance':
                    return {"valid": False, "error": "Промокод не для пополнения баланса"}
        
        # Проверить использование
        if db.check_promocode_used(user_id, promo['id']):
            return {"valid": False, "error": "Промокод уже использован"}
        
        # Проверить лимит
        if promo['max_uses'] != -1 and promo['current_uses'] >= promo['max_uses']:
            return {"valid": False, "error": "Лимит использований исчерпан"}
        
        return {
            "valid": True, 
            "code": promo['code'],
            "type": promo.get('type', 'percent'),
            "value": promo['value']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating promo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/promocode/apply")
async def apply_promo(
    request: ApplyPromoRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Применить промокод (только для balance)"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        promo = db.get_promocode(request.code)
        if not promo:
            return {"success": False, "error": "Промокод не найден"}
        
        # Проверить использование
        if db.check_promocode_used(user_id, promo['id']):
            return {"success": False, "error": "Промокод уже использован"}
        
        # Проверить лимит использований
        if promo['max_uses'] != -1 and promo['current_uses'] >= promo['max_uses']:
            return {"success": False, "error": "Лимит использований промокода исчерпан"}
        
        # Применить только если тип balance
        if promo['type'] == 'balance':
            db.update_user_balance(user_id, promo['value'])
            db.use_promocode(user_id, promo['id'])
            return {"success": True, "message": f"Баланс пополнен на {promo['value']}₽"}
        else:
            return {"success": False, "error": "Этот промокод применяется при оформлении заказа"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying promo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== ORDERS ENDPOINTS ==========

@app.post("/api/orders")
async def create_order(
    request: CreateOrderRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Создать заказ"""
    try:
        logger.info(f"Creating order for user header: {x_telegram_user_id}")
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Получить корзину
        cart = db.get_cart(user_id)
        logger.info(f"Cart for user {user_id}: {len(cart) if cart else 0} items")
        if not cart:
            logger.warning(f"Empty cart for user {user_id} - likely duplicate request")
            raise HTTPException(status_code=400, detail="Cart is empty")
        
        # Проверить остатки на складе для каждого товара в корзине
        conn = db.get_connection()
        cursor = conn.cursor()
        out_of_stock_items = []
        
        for item in cart:
            variant_id = item.get('variant_id')
            cart_quantity = item['cart_quantity']
            
            if variant_id:
                cursor.execute('SELECT quantity FROM product_variants WHERE id = ?', (variant_id,))
                variant = cursor.fetchone()
                
                if not variant or variant['quantity'] < cart_quantity:
                    out_of_stock_items.append({
                        'name': item['name'],
                        'flavor': item.get('flavor', ''),
                        'requested': cart_quantity,
                        'available': variant['quantity'] if variant else 0
                    })
        
        conn.close()
        
        # Если есть товары с недостаточным количеством, вернуть ошибку
        if out_of_stock_items:
            error_message = "Недостаточно товара на складе:\n"
            for item in out_of_stock_items:
                error_message += f"• {item['name']} ({item['flavor']}): запрошено {item['requested']}, доступно {item['available']}\n"
            raise HTTPException(status_code=400, detail=error_message)
        
        # Получить пользователя
        user = db.get_user(user_id)
        
        # Рассчитать стоимость доставки
        delivery_cost = DELIVERY_COST if request.delivery_type == 'delivery' else 0
        
        # Рассчитать промежуточную сумму
        subtotal = sum(item['price'] * item['cart_quantity'] for item in cart)
        
        # Применить автоматические скидки
        cart_items_with_details = []
        for item in cart:
            cart_items_with_details.append({
                'variant_id': item.get('variant_id'),
                'product_id': item.get('id'),
                'category_id': item.get('category_id'),
                'price': item['price'],
                'quantity': item['cart_quantity']
            })
        
        discount_info = db.calculate_discount(cart_items_with_details, subtotal)
        discount = discount_info['total_discount']
        
        # Применить промокод (промокоды суммируются со скидками)
        if request.promocode:
            promo = db.get_promocode(request.promocode)
            if promo and not db.check_promocode_used(user_id, promo['id']):
                # Проверить лимит использований
                if promo['max_uses'] != -1 and promo['current_uses'] >= promo['max_uses']:
                    raise HTTPException(status_code=400, detail="Лимит использований промокода исчерпан")
                
                if promo['type'] == 'percent':
                    promo_discount = subtotal * promo['value'] / 100
                    discount += promo_discount
                elif promo['type'] == 'rub':
                    discount += promo['value']
                
                # Отметить промокод как использованный (промокод автоматически удалится, если исчерпан)
                db.use_promocode(user_id, promo['id'])
        
        # Использовать баланс
        balance_used = 0
        if request.use_balance and user['balance'] > 0:
            subtotal = sum(item['price'] * item['cart_quantity'] for item in cart)
            total_before_balance = subtotal + delivery_cost - discount
            balance_used = min(user['balance'], total_before_balance)
        
        # Рассчитать итоговую сумму
        calc = calculate_order_total(cart, delivery_cost, discount, balance_used)
        
        # Подготовить items для заказа
        order_items = [
            {
                'variant_id': item.get('variant_id'),
                'product_id': item.get('id'),
                'name': item['name'],
                'brand': item.get('brand', ''),
                'price': item['price'],
                'quantity': item['cart_quantity'],
                'flavor': item.get('flavor', '')
            }
            for item in cart
        ]
        
        # Создать заказ
        order_id = db.create_order(
            user_id=user_id,
            items=order_items,
            subtotal=calc['subtotal'],
            delivery_cost=calc['delivery_cost'],
            discount=calc['discount'],
            balance_used=calc['balance_used'],
            total=calc['total'],
            delivery_type=request.delivery_type,
            pickup_location=request.pickup_location,
            delivery_address=request.delivery_address,
            customer_name=request.customer_name,
            customer_phone=request.customer_phone,
            payment_method=request.payment_method,
            promocode=request.promocode,
            cashback_earned=calc['cashback_earned']
        )
        
        # Списать баланс
        if balance_used > 0:
            logger.info(f"Deducting balance {balance_used} from user {user_id}")
            db.update_user_balance(user_id, -balance_used)
        
        # Корзина уже очищена в db.create_order()
        
        logger.info(f"Order #{order_id} created successfully for user {user_id}. Total: {calc['total']}, Cashback: {calc['cashback_earned']}, Balance used: {balance_used}")
        
        return {
            "success": True,
            "order_id": order_id,
            "total": calc['total'],
            "cashback_earned": calc['cashback_earned'],
            "balance_used": balance_used
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/orders/{order_id}/payment-proof")
async def upload_payment_proof(
    order_id: int,
    payment_phone: str = Form(...),
    file: UploadFile = File(...),
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Загрузить подтверждение оплаты (скриншот)"""
    try:
        logger.info(f"Payment proof upload attempt for order {order_id}")
        logger.info(f"X-Telegram-User-Id header: {x_telegram_user_id}")
        
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            logger.error("Failed to get user_id from header")
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        logger.info(f"User ID from header: {user_id}")
        
        # Проверить существование заказа
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        
        if not order:
            logger.error(f"Order {order_id} not found")
            raise HTTPException(status_code=404, detail="Order not found")
        
        logger.info(f"Order found: user_id in order = {order['user_id']}, user_id from header = {user_id}")
        
        # НЕ проверяем владельца - любой авторизованный пользователь может загрузить скриншот
        # (на случай если заказ создался с другим user_id)
        
        # Создать папку если не существует
        screenshots_dir = Path("webapp/static/payment_screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Payment screenshots directory ready: {screenshots_dir}")
        
        # Генерировать уникальное имя файла
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        unique_filename = f"{order_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
        file_path = screenshots_dir / unique_filename
        
        # Сохранить файл
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Обновить заказ в БД
        screenshot_url = f"/static/payment_screenshots/{unique_filename}"
        
        # Проверить наличие полей в таблице
        cursor.execute("PRAGMA table_info(orders)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if 'payment_phone' in columns and 'payment_screenshot' in columns:
            cursor.execute('''
                UPDATE orders 
                SET payment_phone = ?, 
                    payment_screenshot = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (payment_phone, screenshot_url, order_id))
            logger.info(f"Updated order {order_id} with payment proof")
        else:
            logger.warning(f"Fields payment_phone/payment_screenshot not found in orders table. Migration needed!")
            # Файл сохранён, но не можем обновить БД
            # Возвращаем успех, но логируем предупреждение
        
        conn.commit()
        logger.info(f"Payment proof uploaded for order {order_id}: {screenshot_url}")
        
        return {
            "success": True,
            "message": "Подтверждение оплаты загружено",
            "screenshot_url": screenshot_url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading payment proof: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/admin/orders/{order_id}/confirm-payment")
async def confirm_order_payment(
    order_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Подтвердить оплату заказа (только для админов)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Обновить заказ
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE orders 
            SET payment_confirmed = 1
            WHERE id = ?
        ''', (order_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Payment confirmed for order {order_id}")
        
        return {
            "success": True,
            "message": "Оплата подтверждена"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders")
async def get_orders(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить заказы пользователя"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        orders = db.get_user_orders(user_id)
        return {"success": True, "data": orders}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders/{order_id}")
async def get_order(order_id: int, x_telegram_user_id: Optional[str] = Header(None)):
    """Получить заказ по ID"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        order = db.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Проверить что заказ принадлежит пользователю
        if order['user_id'] != user_id:
            # Проверить админа
            telegram_user = db.get_user(user_id)
            if telegram_user and telegram_user.get('telegram_id') not in ADMIN_IDS:
                raise HTTPException(status_code=403, detail="Forbidden")
        
        return {"success": True, "data": order}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== ADMIN ENDPOINTS ==========

def check_admin(x_telegram_user_id: Optional[str]) -> bool:
    """Проверить права администратора"""
    if not x_telegram_user_id:
        return False
    try:
        telegram_id = int(x_telegram_user_id)
        return telegram_id in ADMIN_IDS
    except (ValueError, TypeError):
        return False


@app.get("/api/admin/orders")
async def admin_get_orders(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить все заказы (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        orders = db.get_all_orders()
        return {"success": True, "data": orders}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting admin orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/admin/orders/{order_id}")
async def admin_update_order(
    order_id: int,
    request: UpdateOrderStatusRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Обновить статус заказа (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Если статус completed, начислить кешбек
        if request.status == 'completed':
            db.complete_order_and_add_cashback(order_id)
        else:
            db.update_order_status(order_id, request.status)
        
        return {"success": True, "message": "Order status updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/orders/clear-all")
async def admin_clear_all_orders(x_telegram_user_id: Optional[str] = Header(None)):
    """Удалить ВСЕ заказы (админ) - ОСТОРОЖНО!"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        deleted_count = db.clear_all_orders()
        logger.warning(f"Admin {x_telegram_user_id} cleared ALL orders ({deleted_count} deleted)")
        
        return {
            "success": True, 
            "message": f"All orders cleared ({deleted_count} deleted)",
            "deleted_count": deleted_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing all orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== ADMIN CLIENTS ENDPOINTS ==========

@app.get("/api/admin/clients")
async def admin_get_clients(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить всех клиентов (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        clients = db.get_all_users()
        
        # Форматировать имена для отображения
        for client in clients:
            # Использовать first_name, username или telegram_id для имени
            if client.get('first_name'):
                client['name'] = client['first_name']
            elif client.get('username'):
                client['name'] = f"@{client['username']}"
            else:
                client['name'] = f"User {client.get('telegram_id', client.get('id', 'Unknown'))}"
            
            # Форматировать телефон если есть
            if not client.get('phone'):
                client['phone'] = 'Не указан'
        
        return {"success": True, "data": clients}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting clients: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/profit-stats")
async def admin_get_profit_stats(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить статистику прибыли (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        stats = db.get_profit_statistics()
        return {"success": True, "data": stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profit stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class UpdateClientRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    balance: Optional[float] = None


@app.patch("/api/admin/clients/{client_id}")
async def admin_update_client(
    client_id: int,
    request: UpdateClientRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Обновить клиента (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Обновить информацию
        if request.name or request.phone:
            db.update_user_info(client_id, request.name, request.phone)
        
        # Обновить баланс
        if request.balance is not None:
            db.set_user_balance(client_id, request.balance)
        
        return {"success": True, "message": "Client updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating client: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/clients/{client_id}")
async def admin_delete_client(
    client_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Удалить клиента (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        db.delete_user(client_id)
        return {"success": True, "message": "Client deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting client: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== ADMIN PRODUCTS ENDPOINTS ==========

@app.get("/api/admin/products")
async def admin_get_products(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить все товары (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        products = db.get_products(include_out_of_stock=True)
        return {"success": True, "data": products}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# УДАЛЕНО: старый endpoint, заменён на полный ниже


@app.post("/api/admin/product-photos")
async def admin_upload_product_photo(
    request: Request,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Загрузить фото товара (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Получить form data
        form = await request.form()
        product_id = int(form.get('productId'))
        
        # Если передана ссылка
        image_url = form.get('imageUrl')
        if image_url:
            db.update_product_image(product_id, image_url)
            return {"success": True, "message": "Photo updated"}
        
        # TODO: Если передан файл, сохранить его
        # file = form.get('file')
        # if file:
        #     # Сохранить файл и получить URL
        #     pass
        
        return {"success": False, "error": "No image provided"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading photo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/product-photos/{product_id}")
async def admin_delete_product_photo(
    product_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Удалить фото товара (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        db.delete_product_image(product_id)
        return {"success": True, "message": "Photo deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting photo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== Варианты товаров (Админ) ==========

@app.get("/api/admin/product-variants")
async def admin_get_product_variants(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить все варианты товаров (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        variants = db.get_all_variants()
        return {"success": True, "data": variants}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting variants: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/products-grouped")
async def admin_get_products_grouped(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить товары сгруппированные по брендам (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        grouped = db.get_products_grouped_by_brand()
        return {"success": True, "data": grouped}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting grouped products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class UpdateVariantRequest(BaseModel):
    flavor: Optional[str] = None
    quantity: Optional[int] = None


@app.patch("/api/admin/product-variants/{variant_id}")
async def admin_update_variant(
    variant_id: int,
    request: UpdateVariantRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Обновить вариант товара (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        db.update_variant(
            variant_id, 
            flavor=request.flavor,
            quantity=request.quantity
        )
        
        return {"success": True, "message": "Variant updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating variant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class CreateVariantRequest(BaseModel):
    product_id: int
    flavor: str
    quantity: int


@app.post("/api/admin/product-variants")
async def admin_create_variant(
    request: CreateVariantRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Создать новый вариант товара (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        variant_id = db.add_product_variant(
            request.product_id,
            request.flavor,
            request.quantity
        )
        
        return {"success": True, "message": "Variant created", "variant_id": variant_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating variant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/product-variants/{variant_id}")
async def admin_delete_variant(
    variant_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Удалить вариант товара (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        db.delete_variant(variant_id)
        return {"success": True, "message": "Variant deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting variant: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== Управление товарами (Админ) ==========

class UpdateProductRequest(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    base_price: Optional[float] = None
    price: Optional[float] = None  # Текущая цена (с учетом скидки)
    old_price: Optional[float] = None  # Старая цена (зачеркнутая)
    discount_percent: Optional[float] = None  # Процент скидки (рассчитывается автоматически)
    cost_price: Optional[float] = None  # Себестоимость
    strength: Optional[str] = None
    volume: Optional[str] = None
    battery: Optional[str] = None
    puffs: Optional[str] = None
    is_hot: Optional[bool] = None
    category_id: Optional[int] = None


@app.get("/api/admin/products/{product_id}")
async def admin_get_product(
    product_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Получить информацию о товаре (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        product = db.get_product_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return {"success": True, "data": product}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/admin/products/{product_id}")
async def admin_update_product(
    product_id: int,
    request: UpdateProductRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Обновить товар (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        logger.info(f"Updating product {product_id} with data: {request.dict()}")
        
        # Преобразуем request в dict, убираем None значения
        update_data = {k: v for k, v in request.dict().items() if v is not None}
        
        # Автоматически рассчитываем процент скидки если указаны price и old_price
        if 'price' in update_data and 'old_price' in update_data:
            price = update_data['price']
            old_price = update_data['old_price']
            if old_price and old_price > 0 and price < old_price:
                update_data['discount_percent'] = round(((old_price - price) / old_price) * 100, 1)
            else:
                # Если скидки нет, обнуляем старую цену и процент
                update_data['old_price'] = None
                update_data['discount_percent'] = None
        
        logger.info(f"Filtered update data: {update_data}")
        
        if update_data:
            db.update_product(product_id, **update_data)
            logger.info(f"Product {product_id} updated successfully")
        else:
            logger.warning(f"No data to update for product {product_id}")
        
        return {"success": True, "message": "Product updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating product: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/products/{product_id}")
async def admin_delete_product(
    product_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Удалить товар и все его варианты (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        db.delete_product(product_id)
        return {"success": True, "message": "Product deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting product: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class CreateProductRequest(BaseModel):
    name: str
    brand: Optional[str] = None
    category_id: int
    description: Optional[str] = None
    image_url: Optional[str] = None
    base_price: float
    price: Optional[float] = None  # Текущая цена (если не указана = base_price)
    old_price: Optional[float] = None  # Старая цена (для отображения скидки)
    strength: Optional[str] = None
    volume: Optional[str] = None
    battery: Optional[str] = None
    puffs: Optional[str] = None
    is_hot: bool = False


@app.post("/api/admin/products")
async def admin_create_product(
    request: CreateProductRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Создать новый товар (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Если price не указан, используем base_price
        price = request.price if request.price is not None else request.base_price
        
        # Автоматически рассчитываем процент скидки
        discount_percent = None
        if request.old_price and request.old_price > 0 and price < request.old_price:
            discount_percent = round(((request.old_price - price) / request.old_price) * 100, 1)
        
        product_id = db.add_product(
            name=request.name,
            brand=request.brand,
            category_id=request.category_id,
            description=request.description,
            image_url=request.image_url,
            base_price=request.base_price,
            price=price,
            old_price=request.old_price,
            discount_percent=discount_percent,
            strength=request.strength,
            volume=request.volume,
            battery=request.battery,
            puffs=request.puffs,
            is_hot=request.is_hot
        )
        
        return {"success": True, "message": "Product created", "product_id": product_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating product: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== ADMIN PROMOCODES ENDPOINTS ==========

@app.get("/api/admin/promocodes")
async def admin_get_promocodes(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить все промокоды (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        promos = db.get_all_promocodes()
        return {"success": True, "data": promos}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting promocodes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class CreatePromoRequest(BaseModel):
    code: str
    type: str
    value: float
    maxUses: int = -1


class CreateDiscountRequest(BaseModel):
    name: str
    type: str  # percent, fixed, category, category_fixed
    value: float
    target_id: Optional[int] = None
    min_purchase: float = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    priority: int = 0


class UpdateDiscountRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    value: Optional[float] = None
    target_id: Optional[int] = None
    min_purchase: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    active: Optional[int] = None


class AddProductImageRequest(BaseModel):
    product_id: int
    image_url: str
    display_order: int = 0


class UpdateImagesOrderRequest(BaseModel):
    images: List[Dict[str, int]]  # [{"id": 1, "display_order": 0}, ...]


@app.post("/api/admin/promocodes")
async def admin_create_promo(
    request: CreatePromoRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Создать промокод (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        promo_id = db.create_promocode(
            request.code,
            request.type,
            request.value,
            request.maxUses
        )
        
        return {"success": True, "promo_id": promo_id, "message": "Promo created"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating promo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/promocodes/{promo_id}")
async def admin_delete_promo(
    promo_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Удалить промокод (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        db.delete_promocode(promo_id)
        return {"success": True, "message": "Promo deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting promo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== ADMIN: КАТЕГОРИИ ==========

@app.post("/api/admin/categories")
async def admin_create_category(
    request: Request,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Создать категорию (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        data = await request.json()
        name = data.get('name')
        icon = data.get('icon')
        image_url = data.get('image_url')
        sort_order = data.get('sort_order', 1)
        
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO categories (name, icon, image_url, sort_order)
            VALUES (?, ?, ?, ?)
        ''', (name, icon, image_url, sort_order))
        
        conn.commit()
        category_id = cursor.lastrowid
        conn.close()
        
        logger.info(f"Category created: {name} (ID: {category_id})")
        
        return {
            "success": True,
            "message": "Category created",
            "category_id": category_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating category: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/admin/categories/{category_id}")
async def admin_update_category(
    category_id: int,
    request: Request,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Обновить категорию (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        data = await request.json()
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Проверить существование
        cursor.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Category not found")
        
        # Обновить
        updates = []
        values = []
        
        if 'name' in data:
            updates.append('name = ?')
            values.append(data['name'])
        
        if 'icon' in data:
            updates.append('icon = ?')
            values.append(data['icon'])
        
        if 'image_url' in data:
            updates.append('image_url = ?')
            values.append(data['image_url'])
        
        if 'sort_order' in data:
            updates.append('sort_order = ?')
            values.append(data['sort_order'])
        
        if 'cashback_rate' in data:
            updates.append('cashback_rate = ?')
            values.append(data['cashback_rate'])
        
        if updates:
            values.append(category_id)
            cursor.execute(f'''
                UPDATE categories
                SET {', '.join(updates)}
                WHERE id = ?
            ''', values)
            conn.commit()
        
        conn.close()
        
        logger.info(f"Category updated: {category_id}")
        
        return {
            "success": True,
            "message": "Category updated"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating category: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/categories/{category_id}")
async def admin_delete_category(
    category_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Удалить категорию (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Проверить существование
        cursor.execute('SELECT * FROM categories WHERE id = ?', (category_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Category not found")
        
        # Удалить
        cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Category deleted: {category_id}")
        
        return {
            "success": True,
            "message": "Category deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting category: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== УПРАВЛЕНИЕ СКИДКАМИ (ADMIN) ==========

@app.post("/api/admin/discounts")
async def admin_create_discount(
    request: CreateDiscountRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Создать скидку (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        discount_id = db.create_discount(
            name=request.name,
            discount_type=request.type,
            value=request.value,
            target_id=request.target_id,
            min_purchase=request.min_purchase,
            start_date=request.start_date,
            end_date=request.end_date,
            description=request.description,
            priority=request.priority
        )
        
        return {
            "success": True,
            "discount_id": discount_id,
            "message": "Discount created"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating discount: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/discounts")
async def admin_get_discounts(x_telegram_user_id: Optional[str] = Header(None)):
    """Получить все скидки (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        discounts = db.get_all_discounts()
        return {"discounts": discounts}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting discounts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/discounts/{discount_id}")
async def admin_get_discount(
    discount_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Получить скидку по ID (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        discount = db.get_discount(discount_id)
        if not discount:
            raise HTTPException(status_code=404, detail="Discount not found")
        
        return discount
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting discount: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/admin/discounts/{discount_id}")
async def admin_update_discount(
    discount_id: int,
    request: UpdateDiscountRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Обновить скидку (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Собрать обновления
        updates = request.dict(exclude_unset=True)
        
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        success = db.update_discount(discount_id, **updates)
        
        if not success:
            raise HTTPException(status_code=404, detail="Discount not found")
        
        return {
            "success": True,
            "message": "Discount updated"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating discount: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/discounts/{discount_id}/toggle")
async def admin_toggle_discount(
    discount_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Переключить активность скидки (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        success = db.toggle_discount(discount_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Discount not found")
        
        return {
            "success": True,
            "message": "Discount toggled"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling discount: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/discounts/{discount_id}")
async def admin_delete_discount(
    discount_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Удалить скидку (админ)"""
    try:
        if not check_admin(x_telegram_user_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        success = db.delete_discount(discount_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Discount not found")
        
        return {
            "success": True,
            "message": "Discount deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting discount: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== ПОЛУЧЕНИЕ АКТИВНЫХ СКИДОК (PUBLIC) ==========

@app.get("/api/discounts/active")
async def get_active_discounts():
    """Получить активные скидки (публичный endpoint)"""
    try:
        discounts = db.get_active_discounts()
        return {"discounts": discounts}
    except Exception as e:
        logger.error(f"Error getting active discounts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/products/{product_id}/discount")
async def get_product_discount(product_id: int):
    """Получить скидку для товара"""
    try:
        discount = db.get_product_discount(product_id)
        return {"discount": discount}
    except Exception as e:
        logger.error(f"Error getting product discount: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== HEALTH CHECK ==========

@app.get("/health")
async def health_check():
    """Проверка здоровья API"""
    try:
        # Проверить подключение к БД
        categories = db.get_categories()
        return {
            "status": "healthy",
            "database": "connected",
            "categories_count": len(categories)
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# ======================
# USER MANAGEMENT ENDPOINTS (ADMIN)
# ======================

@app.post("/api/admin/users/{user_id}/reset-balance")
async def admin_reset_user_balance(
    user_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Сбросить баланс пользователя (админ)"""
    try:
        db.reset_user_balance(user_id)
        return {"success": True, "message": "Balance reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting user balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/users/{user_id}/ban")
async def admin_ban_user(
    user_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Забанить пользователя (админ)"""
    try:
        db.ban_user(user_id)
        return {"success": True, "message": "User banned successfully"}
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/users/{user_id}/unban")
async def admin_unban_user(
    user_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Разбанить пользователя (админ)"""
    try:
        db.unban_user(user_id)
        return {"success": True, "message": "User unbanned successfully"}
    except Exception as e:
        logger.error(f"Error unbanning user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ======================
# PRODUCT IMAGES ENDPOINTS
# ======================

@app.get("/api/products/{product_id}/images")
async def get_product_images(product_id: int):
    """Получить все изображения товара"""
    try:
        images = db.get_product_images(product_id)
        return {"success": True, "images": images}
    except Exception as e:
        logger.error(f"Error getting product images: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/admin/products/images")
async def admin_add_product_image(
    request: AddProductImageRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Добавить изображение товара (админ)"""
    try:
        image_id = db.add_product_image(
            request.product_id,
            request.image_url,
            request.display_order
        )
        return {"success": True, "image_id": image_id}
    except Exception as e:
        logger.error(f"Error adding product image: {e}")
        return {"success": False, "error": str(e)}


@app.delete("/api/admin/products/images/{image_id}")
async def admin_delete_product_image(
    image_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Удалить изображение товара (админ)"""
    try:
        success = db.delete_product_image(image_id)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error deleting product image: {e}")
        return {"success": False, "error": str(e)}


@app.put("/api/admin/products/images/reorder")
async def admin_reorder_product_images(
    request: UpdateImagesOrderRequest,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Изменить порядок изображений (админ)"""
    try:
        success = db.update_images_order(request.images)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error reordering images: {e}")
        return {"success": False, "error": str(e)}


# ======================
# PAYMENT SETTINGS
# ======================

@app.get("/api/payment-settings")
async def get_payment_settings(
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Получить настройки оплаты"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM payment_settings WHERE id = 1')
        settings = cursor.fetchone()
        conn.close()
        
        if not settings:
            # Вернуть настройки по умолчанию
            return {
                "success": True,
                "payment_method": "card",
                "card_number": PAYMENT_CARD_NUMBER,
                "card_holder": PAYMENT_CARD_HOLDER,
                "card_bank": PAYMENT_CARD_BANK,
                "phone_number": "+79082840129"
            }
        
        return {
            "success": True,
            "payment_method": settings['payment_method'],
            "card_number": settings['card_number'],
            "card_holder": settings['card_holder'],
            "card_bank": settings['card_bank'],
            "phone_number": settings['phone_number']
        }
    except Exception as e:
        logger.error(f"Error getting payment settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/payment-settings")
async def update_payment_settings(
    settings: dict,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Обновить настройки оплаты (только для админов)"""
    try:
        # Проверить telegram_id напрямую
        if not x_telegram_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        try:
            telegram_id = int(x_telegram_user_id)
        except ValueError:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        if telegram_id not in ADMIN_IDS:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE payment_settings 
            SET payment_method = ?, 
                card_number = ?, 
                card_holder = ?, 
                card_bank = ?,
                phone_number = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
        ''', (
            settings.get('payment_method', 'card'),
            settings.get('card_number', ''),
            settings.get('card_holder', ''),
            settings.get('card_bank', ''),
            settings.get('phone_number', '')
        ))
        
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "Настройки оплаты обновлены"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating payment settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders/{order_id}/payment-info")
async def get_payment_info(
    order_id: int,
    x_telegram_user_id: Optional[str] = Header(None)
):
    """Получить данные для оплаты заказа"""
    try:
        user_id = get_user_id_from_header(x_telegram_user_id)
        if not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Получить заказ
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        
        # Получить настройки оплаты
        cursor.execute('SELECT * FROM payment_settings WHERE id = 1')
        payment_settings = cursor.fetchone()
        conn.close()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Получить сумму к оплате
        amount = order['total'] if order['total'] else order['total_amount']
        comment = f"Заказ #{order_id}"
        
        # Если настройки не найдены, использовать дефолтные
        if not payment_settings:
            payment_method = "card"
            card_number = PAYMENT_CARD_NUMBER
            card_holder = PAYMENT_CARD_HOLDER
            card_bank = PAYMENT_CARD_BANK
            phone_number = "+79082840129"
        else:
            payment_method = payment_settings['payment_method']
            card_number = payment_settings['card_number']
            card_holder = payment_settings['card_holder']
            card_bank = payment_settings['card_bank']
            phone_number = payment_settings['phone_number']
        
        return {
            "success": True,
            "order_id": order_id,
            "amount": amount,
            "payment_method": payment_method,
            "card_number": card_number,
            "card_holder": card_holder,
            "card_bank": card_bank,
            "phone_number": phone_number,
            "comment": comment,
            "payment_data": {
                "method": payment_method,
                "card": card_number,
                "holder": card_holder,
                "bank": card_bank,
                "phone": phone_number,
                "amount": amount,
                "purpose": comment
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating payment info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)

