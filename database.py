"""
Модуль для работы с базой данных SQLite
Полностью переписан с нуля с чистой архитектурой
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных магазина"""
    
    def __init__(self, db_path: str = 'shop.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """Получить подключение к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Инициализация структуры базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица категорий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT,
                cashback_rate REAL DEFAULT 3.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица товаров (без вкусов - они в variants)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                brand TEXT,
                base_price REAL NOT NULL,
                strength TEXT,
                volume TEXT,
                battery TEXT,
                puffs TEXT,
                description TEXT,
                image_url TEXT,
                cashback_rate REAL DEFAULT 3.5,
                is_hot INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица вариантов товара (вкусы)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                flavor TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER DEFAULT 0,
                sku TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                UNIQUE(product_id, flavor)
            )
        ''')
        
        # Индекс для быстрого поиска
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_products_category 
            ON products(category_id)
        ''')
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                phone TEXT,
                balance REAL DEFAULT 0,
                avatar_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица корзины (теперь с вариантами)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                variant_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE,
                UNIQUE(user_id, variant_id)
            )
        ''')
        
        # Таблица избранного (теперь по товарам, а не вариантам)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                UNIQUE(user_id, product_id)
            )
        ''')
        
        # Таблица промокодов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('percent', 'rub', 'balance')),
                value REAL NOT NULL,
                max_uses INTEGER DEFAULT -1,
                current_uses INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица использованных промокодов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS used_promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                promocode_id INTEGER NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (promocode_id) REFERENCES promocodes(id) ON DELETE CASCADE,
                UNIQUE(user_id, promocode_id)
            )
        ''')
        
        # Таблица скидок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('percent', 'fixed', 'category', 'product')),
                value REAL NOT NULL,
                target_id INTEGER,
                min_purchase REAL DEFAULT 0,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                active INTEGER DEFAULT 1,
                priority INTEGER DEFAULT 0,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                items TEXT NOT NULL,
                subtotal REAL DEFAULT 0,
                delivery_cost REAL DEFAULT 0,
                discount REAL DEFAULT 0,
                balance_used REAL DEFAULT 0,
                total REAL DEFAULT 0,
                total_amount REAL DEFAULT 0,
                delivery_type TEXT CHECK(delivery_type IN ('pickup', 'delivery')),
                pickup_location TEXT,
                delivery_address TEXT,
                customer_name TEXT,
                customer_phone TEXT,
                payment_method TEXT CHECK(payment_method IN ('sbp_online', 'sbp_pickup', 'cash', 'balance')),
                promocode TEXT,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'completed', 'cancelled')),
                cashback_earned REAL DEFAULT 0,
                cashback_applied INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица настроек оплаты
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payment_method TEXT DEFAULT 'card',
                card_number TEXT,
                card_holder TEXT,
                card_bank TEXT,
                phone_number TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Инициализировать настройки оплаты по умолчанию
        cursor.execute('SELECT COUNT(*) FROM payment_settings')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO payment_settings (id, payment_method, card_number, card_holder, card_bank, phone_number)
                VALUES (1, 'card', '2202 2063 7098 3657', 'HotSpot', 'Сбербанк', '+79082840129')
            ''')
        
        # Добавить колонку balance_used если её нет (для миграции существующих БД)
        try:
            cursor.execute('ALTER TABLE orders ADD COLUMN balance_used REAL DEFAULT 0')
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Колонка уже существует
        
        # Добавить колонки battery и puffs если их нет (для миграции существующих БД)
        try:
            cursor.execute('ALTER TABLE products ADD COLUMN battery TEXT')
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Колонка уже существует
        
        try:
            cursor.execute('ALTER TABLE products ADD COLUMN puffs TEXT')
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Колонка уже существует
        
        # Обновить кешбек для всех категорий при инициализации
        cursor.execute('UPDATE categories SET cashback_rate = 3.0 WHERE id IN (1, 2, 3)')
        cursor.execute('UPDATE categories SET cashback_rate = 2.0 WHERE id = 4')
        
        conn.commit()
        conn.close()
        
        # Заполнить начальные данные
        self._seed_initial_data()
    
    def _seed_initial_data(self):
        """Заполнение начальных данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверяем, есть ли категории
        cursor.execute('SELECT COUNT(*) FROM categories')
        if cursor.fetchone()[0] == 0:
            # Добавляем категории
            categories = [
                ('Жидкости', '💧', 3.5),
                ('Одноразки', '🔥', 3.5),
                ('Картриджи и Испарители', '⚙️', 3.5),
                ('POD-системы', '📱', 2.5)
            ]
            cursor.executemany(
                'INSERT INTO categories (name, icon, cashback_rate) VALUES (?, ?, ?)',
                categories
            )
            logger.info("Категории созданы")
        
        conn.commit()
        conn.close()
    
    # ========== КАТЕГОРИИ ==========
    
    def get_categories(self) -> List[Dict]:
        """Получить все категории"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM categories ORDER BY id')
        categories = [dict(row) for row in cursor.fetchall()]
        
        # Добавить количество товаров в каждой категории
        for category in categories:
            cursor.execute('''
                SELECT COUNT(DISTINCT p.id) 
                FROM products p
                INNER JOIN product_variants v ON p.id = v.product_id
                WHERE p.category_id = ? AND v.quantity > 0
            ''', (category['id'],))
            category['product_count'] = cursor.fetchone()[0]
        
        conn.close()
        return categories
    
    # ========== ТОВАРЫ ==========
    
    def get_products(self, category_id: Optional[int] = None, 
                     include_out_of_stock: bool = False) -> List[Dict]:
        """Получить товары с вариантами"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Сначала получить товары
        query = 'SELECT * FROM products'
        params = []
        
        if category_id:
            query += ' WHERE category_id = ?'
            params.append(category_id)
        
        query += ' ORDER BY is_hot DESC, name'
        
        cursor.execute(query, params)
        products = []
        
        for row in cursor.fetchall():
            product = dict(row)
            product_id = product['id']
            
            # Получить варианты для этого товара (без цены - она на уровне товара)
            if include_out_of_stock:
                cursor.execute('''
                    SELECT id, flavor, quantity 
                    FROM product_variants 
                    WHERE product_id = ?
                    ORDER BY flavor
                ''', (product_id,))
            else:
                cursor.execute('''
                    SELECT id, flavor, quantity 
                    FROM product_variants 
                    WHERE product_id = ? AND quantity > 0
                    ORDER BY flavor
                ''', (product_id,))
            
            variants = [dict(v) for v in cursor.fetchall()]
            
            # Только если есть варианты в наличии
            if variants or include_out_of_stock:
                product['variants'] = variants
                products.append(product)
        
        conn.close()
        return products
    
    def get_product(self, product_id: int) -> Optional[Dict]:
        """Получить товар по ID с вариантами"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        product = dict(row)
        
        # Получить варианты (без цены - она на уровне товара)
        cursor.execute('''
            SELECT id, flavor, quantity 
            FROM product_variants 
            WHERE product_id = ?
            ORDER BY flavor
        ''', (product_id,))
        
        product['variants'] = [dict(v) for v in cursor.fetchall()]
        
        conn.close()
        return product
    
    def search_products(self, query: str) -> List[Dict]:
        """Поиск товаров с вариантами"""
        conn = self.get_connection()
        cursor = conn.cursor()
        search = f'%{query}%'
        
        # Найти товары по имени, бренду или описанию
        cursor.execute('''
            SELECT DISTINCT p.* 
            FROM products p
            WHERE p.name LIKE ? OR p.brand LIKE ? OR p.description LIKE ?
            ORDER BY p.is_hot DESC, p.name
        ''', (search, search, search))
        
        products = []
        for row in cursor.fetchall():
            product = dict(row)
            product_id = product['id']
            
            # Получить варианты (включая поиск по вкусу, без цены - она на уровне товара)
            cursor.execute('''
                SELECT id, flavor, quantity 
                FROM product_variants 
                WHERE product_id = ? 
                AND (quantity > 0 OR flavor LIKE ?)
                ORDER BY flavor
            ''', (product_id, search))
            
            variants = [dict(v) for v in cursor.fetchall()]
            
            if variants:
                product['variants'] = variants
                products.append(product)
        
        conn.close()
        return products
    
    def add_product(self, category_id: int, name: str, brand: str, 
                    base_price: float, **kwargs) -> int:
        """Добавить основной товар (без вариантов)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверить, существует ли уже такой товар
        cursor.execute('''
            SELECT id FROM products 
            WHERE category_id = ? AND brand = ? AND name = ? 
            AND strength = ? AND volume = ?
        ''', (
            category_id, brand, name,
            kwargs.get('strength', ''),
            kwargs.get('volume', '')
        ))
        
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return existing[0]
        
        # Получить список существующих колонок
        cursor.execute("PRAGMA table_info(products)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Базовые поля
        fields = ['category_id', 'name', 'brand', 'base_price']
        values = [category_id, name, brand, base_price]
        
        # Добавляем опциональные поля, если они существуют в таблице
        optional_fields = {
            'price': kwargs.get('price', base_price),  # По умолчанию = base_price
            'old_price': kwargs.get('old_price'),
            'discount_percent': kwargs.get('discount_percent'),
            'cost_price': kwargs.get('cost_price', 0),  # Себестоимость
            'strength': kwargs.get('strength', ''),
            'volume': kwargs.get('volume', ''),
            'battery': kwargs.get('battery', ''),
            'puffs': kwargs.get('puffs', ''),
            'description': kwargs.get('description', ''),
            'image_url': kwargs.get('image_url'),
            'cashback_rate': kwargs.get('cashback_rate', 3.5),
            'is_hot': kwargs.get('is_hot', 0)
        }
        
        for field, value in optional_fields.items():
            if field in existing_columns:
                fields.append(field)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in values])
        field_names = ', '.join(fields)
        
        cursor.execute(f'''
            INSERT INTO products ({field_names})
            VALUES ({placeholders})
        ''', values)
        
        product_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return product_id
    
    def add_product_variant(self, product_id: int, flavor: str, 
                            price: float, quantity: int) -> int:
        """Добавить вариант товара (вкус)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO product_variants (
                product_id, flavor, price, quantity
            ) VALUES (?, ?, ?, ?)
        ''', (product_id, flavor, price, quantity))
        
        variant_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return variant_id
    
    def update_variant_quantity(self, variant_id: int, quantity_change: int):
        """Обновить количество варианта товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE product_variants 
            SET quantity = quantity + ?
            WHERE id = ?
        ''', (quantity_change, variant_id))
        conn.commit()
        conn.close()
    
    def get_all_variants(self):
        """Получить все варианты товаров с информацией о товаре"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверяем какие колонки есть в таблицах
        cursor.execute("PRAGMA table_info(products)")
        product_columns = {col[1] for col in cursor.fetchall()}
        
        cursor.execute("PRAGMA table_info(product_variants)")
        variant_columns = {col[1] for col in cursor.fetchall()}
        
        # Базовые колонки из вариантов (без price - его больше нет)
        select_fields = [
            'pv.id', 'pv.product_id', 'pv.flavor', 'pv.quantity',
            'p.name', 'p.brand', 'p.description', 'p.image_url', 'p.category_id'
        ]
        
        # Добавляем цену из товара, если она есть
        if 'price' in product_columns:
            select_fields.append('p.price')
        elif 'base_price' in product_columns:
            select_fields.append('p.base_price as price')
        
        # Добавляем опциональные колонки если они есть
        optional_fields = ['strength', 'volume', 'battery', 'puffs', 'old_price', 'discount_percent']
        for field in optional_fields:
            if field in product_columns:
                select_fields.append(f'p.{field}')
        
        query = f'''
            SELECT {', '.join(select_fields)}
            FROM product_variants pv
            JOIN products p ON p.id = pv.product_id
            ORDER BY p.name, pv.flavor
        '''
        
        cursor.execute(query)
        
        variants = []
        for row in cursor.fetchall():
            variant = {
                'id': row[0],
                'product_id': row[1],
                'flavor': row[2],
                'quantity': row[3],
                'name': row[4],
                'brand': row[5] if len(row) > 5 and row[5] else '',
                'description': row[6] if len(row) > 6 and row[6] else '',
                'image_url': row[7] if len(row) > 7 and row[7] else '',
                'category_id': row[8] if len(row) > 8 else None
            }
            
            # Добавляем цену и опциональные поля
            idx = 9
            
            # Цена (если была добавлена в select)
            if 'price' in product_columns or 'base_price' in product_columns:
                variant['price'] = row[idx] if len(row) > idx else 0
                idx += 1
            else:
                variant['price'] = 0
            
            # Опциональные поля
            for field in optional_fields:
                if field in product_columns:
                    variant[field] = row[idx] if len(row) > idx else None
                    idx += 1
                else:
                    variant[field] = None
            
            variants.append(variant)
        
        conn.close()
        return variants
    
    def add_product_variant(self, product_id: int, flavor: str, quantity: int = 0):
        """Добавить вариант товара (только вкус и количество, цена - на товаре)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO product_variants (product_id, flavor, quantity)
            VALUES (?, ?, ?)
        ''', (product_id, flavor, quantity))
        
        variant_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created variant {variant_id} for product {product_id}: {flavor}")
        return variant_id
    
    def update_variant(self, variant_id: int, flavor: str = None, quantity: int = None):
        """Обновить вариант товара (только вкус и количество)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if flavor is not None:
            updates.append("flavor = ?")
            params.append(flavor)
        
        if quantity is not None:
            updates.append("quantity = ?")
            params.append(quantity)
        
        if updates:
            params.append(variant_id)
            cursor.execute(f'''
                UPDATE product_variants 
                SET {', '.join(updates)}
                WHERE id = ?
            ''', params)
            conn.commit()
        
        conn.close()
    
    def delete_variant(self, variant_id: int):
        """Удалить вариант товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM product_variants WHERE id = ?', (variant_id,))
        conn.commit()
        conn.close()
    
    def update_product(self, product_id: int, **kwargs):
        """Обновить основную информацию о товаре"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получить список допустимых колонок
        cursor.execute("PRAGMA table_info(products)")
        valid_columns = [col[1] for col in cursor.fetchall()]
        
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in valid_columns and value is not None:
                updates.append(f"{field} = ?")
                params.append(value)
        
        if updates:
            params.append(product_id)
            query = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
        
        conn.close()
    
    def delete_product(self, product_id: int):
        """Удалить товар и все его варианты"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Удалить все варианты
        cursor.execute('DELETE FROM product_variants WHERE product_id = ?', (product_id,))
        
        # Удалить сам товар
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        
        conn.commit()
        conn.close()
    
    def get_product_by_id(self, product_id: int):
        """Получить товар по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получить список колонок
        cursor.execute("PRAGMA table_info(products)")
        columns = [col[1] for col in cursor.fetchall()]
        
        cursor.execute(f"SELECT * FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        
        if row:
            product = dict(zip(columns, row))
            conn.close()
            return product
        
        conn.close()
        return None
    
    def set_product_discount(self, product_id: int, old_price: float, new_price: float):
        """Установить скидку на товар"""
        discount_percent = round(((old_price - new_price) / old_price) * 100, 1) if old_price > 0 else 0
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE products 
            SET old_price = ?, price = ?, discount_percent = ?
            WHERE id = ?
        ''', (old_price, new_price, discount_percent, product_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Set discount on product {product_id}: {old_price}₽ -> {new_price}₽ ({discount_percent}%)")
    
    def remove_product_discount(self, product_id: int):
        """Убрать скидку с товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE products 
            SET old_price = NULL, discount_percent = NULL
            WHERE id = ?
        ''', (product_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Removed discount from product {product_id}")
    
    def get_products_grouped_by_brand(self):
        """Получить товары сгруппированные по брендам"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получить список колонок
        cursor.execute("PRAGMA table_info(products)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Получить все товары
        cursor.execute("SELECT * FROM products ORDER BY brand, name")
        products = cursor.fetchall()
        
        # Получить все варианты для каждого товара
        cursor.execute("""
            SELECT product_id, id, flavor, quantity 
            FROM product_variants 
            ORDER BY product_id, flavor
        """)
        variants = cursor.fetchall()
        
        conn.close()
        
        # Группировка по брендам
        grouped = {}
        
        for product_row in products:
            product = dict(zip(columns, product_row))
            brand = product.get('brand', 'Без бренда')
            
            if brand not in grouped:
                grouped[brand] = {
                    'brand': brand,
                    'products': []
                }
            
            # Найти варианты для этого товара (без цены - она теперь на уровне товара)
            product_variants = [
                {
                    'id': v[1],
                    'flavor': v[2],
                    'quantity': v[3]
                }
                for v in variants if v[0] == product['id']
            ]
            
            product['variants'] = product_variants
            grouped[brand]['products'].append(product)
        
        return list(grouped.values())
    
    def set_product_quantity(self, product_id: int, quantity: int):
        """Установить количество товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products 
            SET quantity = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (quantity, product_id))
        conn.commit()
        conn.close()
    
    def update_product_flavor(self, product_id: int, flavor: str):
        """Обновить вкус товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products 
            SET flavor = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (flavor, product_id))
        conn.commit()
        conn.close()
    
    def update_product_image(self, product_id: int, image_url: str):
        """Обновить изображение товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products 
            SET image_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (image_url, product_id))
        conn.commit()
        conn.close()
    
    def delete_product_image(self, product_id: int):
        """Удалить изображение товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products 
            SET image_url = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (product_id,))
        conn.commit()
        conn.close()
    
    def delete_all_products(self):
        """Удалить все товары"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM products')
        conn.commit()
        conn.close()
    
    # ========== ПОЛЬЗОВАТЕЛИ ==========
    
    def get_or_create_user(self, telegram_id: int, username: str = None, 
                          first_name: str = None) -> int:
        """Получить или создать пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
        
        if user:
            user_id = user['id']
            # Обновить данные если изменились
            if username or first_name:
                cursor.execute('''
                    UPDATE users 
                    SET username = COALESCE(?, username),
                        first_name = COALESCE(?, first_name),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (username, first_name, user_id))
                conn.commit()
        else:
            cursor.execute('''
                INSERT INTO users (telegram_id, username, first_name)
                VALUES (?, ?, ?)
            ''', (telegram_id, username, first_name))
            user_id = cursor.lastrowid
            conn.commit()
        
        conn.close()
        return user_id
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Получить пользователя по Telegram ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить пользователя по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None
    
    def update_user_balance(self, user_id: int, amount: float):
        """Обновить баланс пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (amount, user_id))
        conn.commit()
        conn.close()
    
    def set_user_balance(self, user_id: int, balance: float):
        """Установить баланс пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET balance = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (balance, user_id))
        conn.commit()
        conn.close()
    
    def reset_user_balance(self, user_id: int):
        """Сбросить баланс пользователя до нуля"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET balance = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (user_id,))
        conn.commit()
        conn.close()
    
    def ban_user(self, user_id: int):
        """Забанить пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET is_banned = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (user_id,))
        conn.commit()
        conn.close()
    
    def unban_user(self, user_id: int):
        """Разбанить пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users 
            SET is_banned = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (user_id,))
        conn.commit()
        conn.close()
    
    def update_user_info(self, user_id: int, name: str = None, phone: str = None):
        """Обновить информацию о пользователе"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if name is not None:
            updates.append('first_name = ?')
            params.append(name)
        
        if phone is not None:
            updates.append('phone = ?')
            params.append(phone)
        
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            params.append(user_id)
            
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
        
        conn.close()
    
    def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей (для админа)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.*, COUNT(DISTINCT o.id) as orderCount
            FROM users u
            LEFT JOIN orders o ON u.id = o.user_id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        ''')
        
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users
    
    def delete_user(self, user_id: int):
        """Удалить пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
    
    # ========== КОРЗИНА ==========
    
    def add_to_cart(self, user_id: int, variant_id: int, quantity: int = 1):
        """Добавить вариант товара в корзину"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO cart (user_id, variant_id, quantity)
                VALUES (?, ?, ?)
            ''', (user_id, variant_id, quantity))
        except sqlite3.IntegrityError:
            # Товар уже в корзине, обновляем количество
            cursor.execute('''
                UPDATE cart 
                SET quantity = quantity + ?
                WHERE user_id = ? AND variant_id = ?
            ''', (quantity, user_id, variant_id))
        
        conn.commit()
        conn.close()
    
    def update_cart_item(self, user_id: int, variant_id: int, quantity: int):
        """Обновить количество товара в корзине"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if quantity <= 0:
            cursor.execute('''
                DELETE FROM cart 
                WHERE user_id = ? AND variant_id = ?
            ''', (user_id, variant_id))
        else:
            cursor.execute('''
                UPDATE cart 
                SET quantity = ?
                WHERE user_id = ? AND variant_id = ?
            ''', (quantity, user_id, variant_id))
        
        conn.commit()
        conn.close()
    
    def get_cart(self, user_id: int) -> List[Dict]:
        """Получить корзину пользователя с вариантами"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверяем какие поля есть в product_variants
        cursor.execute("PRAGMA table_info(product_variants)")
        variant_columns = {row[1] for row in cursor.fetchall()}
        
        # Цена теперь на уровне товара, а не варианта
        cursor.execute('''
            SELECT 
                c.id as cart_id,
                c.quantity as cart_quantity,
                v.id as variant_id,
                v.flavor,
                v.quantity as stock_quantity,
                p.id as product_id,
                p.id,
                p.name,
                p.brand,
                p.category_id,
                p.price,
                p.base_price,
                p.old_price,
                p.discount_percent,
                p.description,
                p.image_url,
                p.is_hot,
                p.cashback_rate,
                p.created_at,
                p.updated_at
            FROM cart c
            JOIN product_variants v ON c.variant_id = v.id
            JOIN products p ON v.product_id = p.id
            WHERE c.user_id = ?
            ORDER BY c.created_at DESC
        ''', (user_id,))
        items = [dict(row) for row in cursor.fetchall()]
        
        # Добавляем цену из товара, если её нет в результате
        for item in items:
            if 'price' not in item or item.get('price') is None:
                item['price'] = item.get('price') or item.get('base_price', 0)
        
        conn.close()
        return items
    
    def remove_from_cart(self, user_id: int, variant_id: int):
        """Удалить вариант товара из корзины"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM cart 
            WHERE user_id = ? AND variant_id = ?
        ''', (user_id, variant_id))
        conn.commit()
        conn.close()
    
    def clear_cart(self, user_id: int):
        """Очистить корзину"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM cart WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    
    # ========== ИЗБРАННОЕ ==========
    
    def toggle_favorite(self, user_id: int, product_id: int) -> bool:
        """Добавить/удалить из избранного. Возвращает True если добавлено"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM favorites 
            WHERE user_id = ? AND product_id = ?
        ''', (user_id, product_id))
        
        if cursor.fetchone():
            # Удалить
            cursor.execute('''
                DELETE FROM favorites 
                WHERE user_id = ? AND product_id = ?
            ''', (user_id, product_id))
            added = False
        else:
            # Добавить
            cursor.execute('''
                INSERT INTO favorites (user_id, product_id)
                VALUES (?, ?)
            ''', (user_id, product_id))
            added = True
        
        conn.commit()
        conn.close()
        return added
    
    def get_favorites(self, user_id: int) -> List[Dict]:
        """Получить избранное пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.* 
            FROM favorites f
            JOIN products p ON f.product_id = p.id
            WHERE f.user_id = ?
            ORDER BY f.created_at DESC
        ''', (user_id,))
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items
    
    def is_favorite(self, user_id: int, product_id: int) -> bool:
        """Проверить, в избранном ли товар"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM favorites 
            WHERE user_id = ? AND product_id = ?
        ''', (user_id, product_id))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    # ========== ПРОМОКОДЫ ==========
    
    def get_promocode(self, code: str) -> Optional[Dict]:
        """Получить промокод"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM promocodes 
            WHERE UPPER(code) = UPPER(?) AND active = 1
        ''', (code,))
        promo = cursor.fetchone()
        conn.close()
        return dict(promo) if promo else None
    
    def check_promocode_used(self, user_id: int, promocode_id: int) -> bool:
        """Проверить, использовал ли пользователь промокод"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM used_promocodes 
            WHERE user_id = ? AND promocode_id = ?
        ''', (user_id, promocode_id))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def use_promocode(self, user_id: int, promocode_id: int) -> bool:
        """Отметить промокод как использованный"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Добавить запись об использовании
            cursor.execute('''
                INSERT INTO used_promocodes (user_id, promocode_id)
                VALUES (?, ?)
            ''', (user_id, promocode_id))
            
            # Увеличить счетчик использований
            cursor.execute('''
                UPDATE promocodes 
                SET current_uses = current_uses + 1
                WHERE id = ?
            ''', (promocode_id,))
            
            # Получить информацию о промокоде
            cursor.execute('''
                SELECT current_uses, max_uses FROM promocodes WHERE id = ?
            ''', (promocode_id,))
            promo_info = cursor.fetchone()
            
            # Если превышено количество использований - удалить промокод
            if promo_info and promo_info[1] != -1:  # max_uses != -1 (не безлимитный)
                current_uses = promo_info[0]
                max_uses = promo_info[1]
                
                if current_uses >= max_uses:
                    logger.info(f"Промокод {promocode_id} исчерпан ({current_uses}/{max_uses}), удаляем...")
                    
                    # Удаляем промокод
                    cursor.execute('DELETE FROM promocodes WHERE id = ?', (promocode_id,))
                    logger.info(f"Промокод {promocode_id} успешно удален")
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def create_promocode(self, code: str, promo_type: str, value: float, 
                        max_uses: int = -1) -> int:
        """Создать промокод"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO promocodes (code, type, value, max_uses)
            VALUES (UPPER(?), ?, ?, ?)
        ''', (code, promo_type, value, max_uses))
        promo_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return promo_id
    
    def get_all_promocodes(self) -> List[Dict]:
        """Получить все промокоды (для админа)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM promocodes 
            ORDER BY created_at DESC
        ''')
        promos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return promos
    
    def delete_promocode(self, promo_id: int):
        """Удалить промокод"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM promocodes WHERE id = ?', (promo_id,))
        conn.commit()
        conn.close()
    
    # ========== ЗАКАЗЫ ==========
    
    def create_order(self, user_id: int, items: List[Dict], subtotal: float,
                    delivery_cost: float, discount: float, total: float,
                    **kwargs) -> int:
        """Создать заказ"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        items_json = json.dumps(items, ensure_ascii=False)
        
        # total_amount - полная стоимость заказа (до вычета баланса)
        total_amount = subtotal + delivery_cost - discount
        
        cursor.execute('''
            INSERT INTO orders (
                user_id, items, subtotal, delivery_cost, discount, balance_used, total, total_amount,
                delivery_type, pickup_location, delivery_address,
                customer_name, customer_phone, payment_method, promocode,
                cashback_earned
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, items_json, subtotal, delivery_cost, discount, kwargs.get('balance_used', 0), total, total_amount,
            kwargs.get('delivery_type'),
            kwargs.get('pickup_location'),
            kwargs.get('delivery_address'),
            kwargs.get('customer_name'),
            kwargs.get('customer_phone'),
            kwargs.get('payment_method'),
            kwargs.get('promocode'),
            kwargs.get('cashback_earned', 0)
        ))
        
        order_id = cursor.lastrowid
        
        # Сохранить телефон пользователя если это первый заказ
        customer_phone = kwargs.get('customer_phone')
        if customer_phone:
            # Проверить есть ли у пользователя телефон
            cursor.execute('SELECT phone FROM users WHERE id = ?', (user_id,))
            user_data = cursor.fetchone()
            if user_data and not user_data['phone']:
                # Обновить телефон пользователя
                cursor.execute('UPDATE users SET phone = ? WHERE id = ?', (customer_phone, user_id))
        
        # Списать товары со склада (обновляем варианты, а не товары)
        for item in items:
            # Используем variant_id вместо product_id
            variant_id = item.get('variant_id') or item.get('product_id')
            quantity = item.get('quantity', 1)
            
            cursor.execute('''
                UPDATE product_variants 
                SET quantity = quantity - ?
                WHERE id = ?
            ''', (quantity, variant_id))
        
        # Очистить корзину пользователя после создания заказа
        cursor.execute('DELETE FROM cart WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return order_id
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        """Получить заказ"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        order = cursor.fetchone()
        conn.close()
        
        if order:
            order_dict = dict(order)
            order_dict['items'] = json.loads(order_dict['items'])
            return order_dict
        return None
    
    def get_user_orders(self, user_id: int) -> List[Dict]:
        """Получить заказы пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM orders 
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        for order in orders:
            order['items'] = json.loads(order['items'])
        
        return orders
    
    def get_all_orders(self) -> List[Dict]:
        """Получить все заказы (для админа)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.*, u.username, u.first_name
            FROM orders o
            JOIN users u ON o.user_id = u.id
            ORDER BY o.created_at DESC
        ''')
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        for order in orders:
            order['items'] = json.loads(order['items'])
        
        return orders
    
    def update_order_status(self, order_id: int, status: str):
        """Обновить статус заказа"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Если заказ отменяется, вернуть баланс пользователю
        if status == 'cancelled':
            cursor.execute('''
                SELECT user_id, balance_used
                FROM orders 
                WHERE id = ?
            ''', (order_id,))
            order = cursor.fetchone()
            
            if order and order['balance_used'] > 0:
                # Вернуть баланс пользователю
                cursor.execute('''
                    UPDATE users 
                    SET balance = balance + ?
                    WHERE id = ?
                ''', (order['balance_used'], order['user_id']))
        
        cursor.execute('''
            UPDATE orders 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, order_id))
        conn.commit()
        conn.close()
    
    def complete_order_and_add_cashback(self, order_id: int):
        """Завершить заказ и начислить кешбек"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверить наличие полей кешбека
        cursor.execute("PRAGMA table_info(orders)")
        columns = {row[1] for row in cursor.fetchall()}
        has_cashback = 'cashback_earned' in columns and 'cashback_applied' in columns
        
        if has_cashback:
            # Получить заказ с кешбеком
            cursor.execute('''
                SELECT user_id, cashback_earned, cashback_applied
                FROM orders 
                WHERE id = ?
            ''', (order_id,))
            order = cursor.fetchone()
            
            if order:
                # Преобразуем sqlite3.Row в dict для использования .get()
                order_dict = dict(order)
                
                if not order_dict.get('cashback_applied'):
                    user_id = order_dict['user_id']
                    cashback = order_dict.get('cashback_earned', 0)
                    
                    # Начислить кешбек
                    if cashback and cashback > 0:
                        print(f"[CASHBACK] Adding {cashback}₽ to user {user_id} balance for order {order_id}")
                        cursor.execute('''
                            UPDATE users 
                            SET balance = balance + ?
                            WHERE id = ?
                        ''', (cashback, user_id))
                    
                    # Обновить заказ
                    cursor.execute('''
                        UPDATE orders 
                        SET status = 'completed', 
                            cashback_applied = 1
                        WHERE id = ?
                    ''', (order_id,))
        else:
            # Если нет полей кешбека, просто обновить статус
            cursor.execute('''
                UPDATE orders 
                SET status = 'completed'
                WHERE id = ?
            ''', (order_id,))
        
        conn.commit()
        conn.close()
        return True
    
    # ================== УПРАВЛЕНИЕ СКИДКАМИ ==================
    
    def create_discount(self, name: str, discount_type: str, value: float, 
                       target_id: Optional[int] = None, min_purchase: float = 0,
                       start_date: Optional[str] = None, end_date: Optional[str] = None,
                       description: Optional[str] = None, priority: int = 0) -> int:
        """
        Создать новую скидку
        
        Types:
        - percent: процентная скидка на весь заказ
        - fixed: фиксированная скидка на заказ
        - category: скидка на категорию (target_id = category_id)
        - product: скидка на товар (target_id = product_id)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO discounts (name, type, value, target_id, min_purchase, 
                                  start_date, end_date, description, priority, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (name, discount_type, value, target_id, min_purchase, 
              start_date, end_date, description, priority))
        
        discount_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created discount: {name} (ID: {discount_id})")
        return discount_id
    
    def get_all_discounts(self) -> List[Dict]:
        """Получить все скидки"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT d.*, 
                   CASE 
                       WHEN d.type = 'category' THEN c.name
                       WHEN d.type = 'product' THEN p.name
                       ELSE NULL
                   END as target_name
            FROM discounts d
            LEFT JOIN categories c ON d.type = 'category' AND d.target_id = c.id
            LEFT JOIN products p ON d.type = 'product' AND d.target_id = p.id
            ORDER BY d.priority DESC, d.created_at DESC
        ''')
        
        discounts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return discounts
    
    def get_active_discounts(self) -> List[Dict]:
        """Получить активные скидки"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT d.*, 
                   CASE 
                       WHEN d.type = 'category' THEN c.name
                       WHEN d.type = 'product' THEN p.name
                       ELSE NULL
                   END as target_name
            FROM discounts d
            LEFT JOIN categories c ON d.type = 'category' AND d.target_id = c.id
            LEFT JOIN products p ON d.type = 'product' AND d.target_id = p.id
            WHERE d.active = 1
                AND (d.start_date IS NULL OR datetime(d.start_date) <= datetime('now'))
                AND (d.end_date IS NULL OR datetime(d.end_date) >= datetime('now'))
            ORDER BY d.priority DESC
        ''')
        
        discounts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return discounts
    
    def get_discount(self, discount_id: int) -> Optional[Dict]:
        """Получить скидку по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT d.*, 
                   CASE 
                       WHEN d.type = 'category' THEN c.name
                       WHEN d.type = 'product' THEN p.name
                       ELSE NULL
                   END as target_name
            FROM discounts d
            LEFT JOIN categories c ON d.type = 'category' AND d.target_id = c.id
            LEFT JOIN products p ON d.type = 'product' AND d.target_id = p.id
            WHERE d.id = ?
        ''', (discount_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def update_discount(self, discount_id: int, **kwargs) -> bool:
        """Обновить скидку"""
        allowed_fields = ['name', 'type', 'value', 'target_id', 'min_purchase', 
                         'start_date', 'end_date', 'active', 'priority', 'description']
        
        updates = []
        values = []
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(discount_id)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f'''
            UPDATE discounts 
            SET {", ".join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', values)
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def delete_discount(self, discount_id: int) -> bool:
        """Удалить скидку"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM discounts WHERE id = ?', (discount_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted discount ID: {discount_id}")
        return success
    
    def toggle_discount(self, discount_id: int) -> bool:
        """Переключить активность скидки"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE discounts 
            SET active = NOT active, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (discount_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def calculate_discount(self, cart_items: List[Dict], subtotal: float) -> Dict:
        """
        Рассчитать применимые скидки для корзины
        Возвращает: {
            'total_discount': float,
            'applied_discounts': [{'id', 'name', 'amount'}],
            'discounted_items': {variant_id: discount_amount}
        }
        """
        active_discounts = self.get_active_discounts()
        
        total_discount = 0
        applied_discounts = []
        discounted_items = {}
        
        # Сортируем скидки по приоритету
        active_discounts.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        for discount in active_discounts:
            # Проверка минимальной суммы покупки
            if discount.get('min_purchase', 0) > subtotal:
                continue
            
            discount_amount = 0
            
            if discount['type'] == 'percent':
                # Процентная скидка на весь заказ
                discount_amount = subtotal * (discount['value'] / 100)
                
            elif discount['type'] == 'fixed':
                # Фиксированная скидка на заказ
                discount_amount = min(discount['value'], subtotal)
                
            elif discount['type'] == 'category':
                # Скидка на категорию
                for item in cart_items:
                    if item.get('category_id') == discount['target_id']:
                        item_discount = item['price'] * item['quantity'] * (discount['value'] / 100)
                        discount_amount += item_discount
                        discounted_items[item['variant_id']] = discounted_items.get(item['variant_id'], 0) + item_discount
                        
            elif discount['type'] == 'product':
                # Скидка на конкретный товар
                for item in cart_items:
                    if item.get('product_id') == discount['target_id']:
                        item_discount = item['price'] * item['quantity'] * (discount['value'] / 100)
                        discount_amount += item_discount
                        discounted_items[item['variant_id']] = discounted_items.get(item['variant_id'], 0) + item_discount
            
            if discount_amount > 0:
                total_discount += discount_amount
                applied_discounts.append({
                    'id': discount['id'],
                    'name': discount['name'],
                    'amount': round(discount_amount, 2)
                })
        
        return {
            'total_discount': round(total_discount, 2),
            'applied_discounts': applied_discounts,
            'discounted_items': discounted_items
        }
    
    def get_product_discount(self, product_id: int) -> Optional[Dict]:
        """Получить активную скидку для конкретного товара"""
        active_discounts = self.get_active_discounts()
        
        for discount in active_discounts:
            if discount['type'] == 'product' and discount['target_id'] == product_id:
                return discount
        
        return None
    
    def get_category_discount(self, category_id: int) -> Optional[Dict]:
        """Получить активную скидку для категории"""
        active_discounts = self.get_active_discounts()
        
        for discount in active_discounts:
            if discount['type'] == 'category' and discount['target_id'] == category_id:
                return discount
        
        return None


    # ======================
    # PRODUCT IMAGES
    # ======================
    
    def get_product_images(self, product_id: int) -> List[Dict]:
        """Получить все изображения товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, product_id, image_url, display_order
            FROM product_images
            WHERE product_id = ?
            ORDER BY display_order ASC, id ASC
        ''', (product_id,))
        
        images = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return images
    
    def add_product_image(self, product_id: int, image_url: str, display_order: int = 0) -> int:
        """Добавить изображение товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO product_images (product_id, image_url, display_order)
            VALUES (?, ?, ?)
        ''', (product_id, image_url, display_order))
        
        image_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return image_id
    
    def delete_product_image(self, image_id: int) -> bool:
        """Удалить изображение товара"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM product_images WHERE id = ?', (image_id,))
        affected = cursor.rowcount
        
        conn.commit()
        conn.close()
        return affected > 0
    
    def update_images_order(self, images_data: List[Dict]) -> bool:
        """Обновить порядок изображений
        images_data: [{"id": 1, "display_order": 0}, {"id": 2, "display_order": 1}, ...]
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        for img in images_data:
            cursor.execute('''
                UPDATE product_images
                SET display_order = ?
                WHERE id = ?
            ''', (img['display_order'], img['id']))
        
        conn.commit()
        conn.close()
        return True
    def clear_all_orders(self) -> int:
        """Удалить ВСЕ заказы из базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Получить количество заказов перед удалением
            cursor.execute('SELECT COUNT(*) as count FROM orders')
            count = cursor.fetchone()['count']
            
            # Удалить все заказы
            cursor.execute('DELETE FROM orders')
            
            conn.commit()
            logger.warning(f"Cleared ALL orders from database ({count} deleted)")
            return count
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error clearing all orders: {e}")
            raise
        finally:
            conn.close()
    
    def get_profit_statistics(self) -> Dict[str, Any]:
        """Получить статистику прибыли"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Получаем все завершённые заказы
            cursor.execute('''
                SELECT 
                    o.id,
                    o.items,
                    o.subtotal,
                    o.total,
                    o.discount,
                    o.balance_used,
                    o.created_at
                FROM orders o
                WHERE o.status = 'completed'
            ''')
            
            orders = [dict(row) for row in cursor.fetchall()]
            
            total_revenue = 0  # Выручка (что получили)
            total_cost = 0     # Себестоимость (что потратили на закупку)
            total_discount_spent = 0
            
            for order in orders:
                items = json.loads(order['items']) if isinstance(order['items'], str) else order['items']
                
                # Рассчитываем выручку и себестоимость по каждому товару
                for item in items:
                    product_id = item.get('product_id')
                    quantity = item.get('quantity', 1)
                    price = item.get('price', 0)
                    
                    # Выручка = цена × количество
                    total_revenue += price * quantity
                    
                    # Получаем себестоимость товара
                    cursor.execute('SELECT cost_price FROM products WHERE id = ?', (product_id,))
                    product = cursor.fetchone()
                    cost_price = product['cost_price'] if product and product['cost_price'] else 0
                    
                    # Себестоимость = себестоимость × количество
                    total_cost += cost_price * quantity
                
                # Скидки и использованный баланс
                discount = order.get('discount', 0) or 0
                balance_used = order.get('balance_used', 0) or 0
                
                total_discount_spent += discount + balance_used
            
            # Валовая прибыль = Выручка - Себестоимость
            gross_profit = total_revenue - total_cost
            
            # Чистая прибыль = Валовая прибыль - Скидки - Баланс
            # (скидки и баланс - это наши расходы)
            net_profit = gross_profit - total_discount_spent
            
            return {
                'gross_profit': round(gross_profit, 2),  # Валовая прибыль
                'discount_spent': round(total_discount_spent, 2),  # Потрачено на акции
                'net_profit': round(net_profit, 2),  # Чистая прибыль
                'orders_count': len(orders),
                'revenue': round(total_revenue, 2),  # Для отладки
                'cost': round(total_cost, 2)  # Для отладки
            }
            
        except Exception as e:
            logger.error(f"Error calculating profit statistics: {e}")
            return {
                'gross_profit': 0,
                'discount_spent': 0,
                'net_profit': 0,
                'orders_count': 0
            }
        finally:
            conn.close()


if __name__ == '__main__':
    # Тестирование
    db = Database()
    print("✅ База данных инициализирована успешно!")
    print(f"📊 Категорий: {len(db.get_categories())}")

