/**
 * HotSpot Shop - Веб-приложение
 * Полностью новая реализация с чистой архитектурой
 */

// ========== Конфигурация ==========
const API_BASE = window.location.origin;
const DEBUG = true;

// ========== Глобальное состояние ==========
const state = {
    user: null,
    telegramUserId: null,
    categories: [],
    products: [],
    cart: [],
    favorites: [],
    currentPage: 'home',
    pageHistory: [],
    selectedProduct: null,
    theme: 'light'
};

// ========== Утилиты ==========
const utils = {
    log: (message, data) => {
        if (DEBUG) console.log(`[HotSpot] ${message}`, data || '');
    },
    
    showLoader: () => {
        document.getElementById('loader').classList.remove('hidden');
    },
    
    hideLoader: () => {
        document.getElementById('loader').classList.add('hidden');
    },
    
    showToast: (message, type = 'success') => {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = `toast show ${type}`;
        
        setTimeout(() => {
            toast.className = 'toast';
        }, 3000);
    },
    
    formatPrice: (price) => {
        const numPrice = parseFloat(price);
        if (isNaN(numPrice) || numPrice === null || numPrice === undefined) {
            return '0₽';
        }
        return `${Math.round(numPrice)}₽`;
    },
    
    getInitials: (name) => {
        if (!name) return 'П';
        return name.charAt(0).toUpperCase();
    },
    
    createParticles: (x, y, isAdding) => {
        const particleCount = 8;
        const emoji = isAdding ? '❤️' : '💔';
        
        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.textContent = emoji;
            particle.style.left = x + 'px';
            particle.style.top = y + 'px';
            
            // Случайное направление
            const angle = (Math.PI * 2 * i) / particleCount;
            const velocity = 50 + Math.random() * 50;
            const offsetX = Math.cos(angle) * velocity;
            const offsetY = Math.sin(angle) * velocity;
            
            particle.style.setProperty('--offset-x', offsetX + 'px');
            particle.style.setProperty('--offset-y', offsetY + 'px');
            
            document.body.appendChild(particle);
            
            setTimeout(() => {
                particle.remove();
            }, 1000);
        }
    }
};

// ========== API ==========
const api = {
    async request(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        if (state.telegramUserId) {
            headers['X-Telegram-User-Id'] = state.telegramUserId;
        }
        
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    },
    
    // Categories & Products
    getCategories: () => api.request('/api/categories'),
    getProducts: (categoryId) => api.request(`/api/products${categoryId ? `?category_id=${categoryId}` : ''}`),
    getProduct: (id) => api.request(`/api/products/${id}`),
    searchProducts: (query) => api.request(`/api/search?q=${encodeURIComponent(query)}`),
    
    // User
    getUser: (userId) => api.request(`/api/user?user_id=${userId}`),
    
    // Cart
    getCart: () => api.request('/api/cart'),
    addToCart: (productId, quantity = 1) => api.request('/api/cart/add', {
        method: 'POST',
        body: JSON.stringify({ product_id: productId, quantity })
    }),
    updateCart: (productId, quantity) => api.request('/api/cart/update', {
        method: 'POST',
        body: JSON.stringify({ product_id: productId, quantity })
    }),
    removeFromCart: (productId) => api.request('/api/cart/remove', {
        method: 'POST',
        body: JSON.stringify({ product_id: productId })
    }),
    
    // Favorites
    getFavorites: () => api.request('/api/favorites'),
    toggleFavorite: (productId) => api.request('/api/favorites/toggle', {
        method: 'POST',
        body: JSON.stringify({ product_id: productId })
    }),
    
    // Orders
    createOrder: (orderData) => api.request('/api/orders', {
        method: 'POST',
        body: JSON.stringify(orderData)
    }),
    getOrders: () => api.request('/api/orders'),
    
    // Promocodes
    validatePromo: (code) => api.request('/api/promocode/validate', {
        method: 'POST',
        body: JSON.stringify({ code })
    }),
    applyPromo: (code) => api.request('/api/promocode/apply', {
        method: 'POST',
        body: JSON.stringify({ code })
    })
};

// ========== UI Компоненты ==========
const components = {
    productCard: (product) => {
        const isFavorite = state.favorites.some(f => f.id === product.id);
        const stockClass = product.quantity < 3 ? 'low' : '';
        const favoriteClass = isFavorite ? 'is-favorite' : '';
        
        return `
            <div class="product-card ${favoriteClass}" data-product-id="${product.id}">
                ${product.is_hot ? '<div class="product-badge"><i class="ph ph-fire"></i>ХИТ</div>' : ''}
                <div class="product-image">
                    ${product.image_url ? `<img src="${product.image_url}" alt="${product.name}" style="width:100%;height:100%;object-fit:cover;border-radius:8px;">` : '<i class="ph ph-package"></i>'}
                </div>
                ${product.brand ? `<div class="product-brand">${product.brand}</div>` : ''}
                <div class="product-name">${product.name}</div>
                ${product.flavor ? `<div class="product-flavor">${product.flavor}</div>` : ''}
                <div class="product-badges">
                    ${product.strength ? `<span class="badge-item">${product.strength}</span>` : ''}
                    ${product.volume ? `<span class="badge-item">${product.volume}</span>` : ''}
                    ${product.cashback ? `<span class="badge-item">+${product.cashback}₽</span>` : ''}
                </div>
                <div class="product-footer">
                    <div class="product-price">${utils.formatPrice(product.price)}</div>
                    <div class="product-stock ${stockClass}">${product.quantity} шт</div>
                </div>
                <div class="product-actions">
                    <button class="btn-icon favorite ${isFavorite ? 'active' : ''}" data-product-id="${product.id}">
                        <i class="ph ${isFavorite ? 'ph-heart-fill' : 'ph-heart'}"></i>
                    </button>
                    <button class="btn-primary add-to-cart" data-product-id="${product.id}">
                        <i class="ph ph-shopping-cart"></i>
                        В корзину
                    </button>
                </div>
            </div>
        `;
    },
    
    categoryCard: (category) => {
        return `
            <div class="category-card" data-category-id="${category.id}">
                <div class="category-icon">${category.icon}</div>
                <div class="category-name">${category.name}</div>
                <div class="category-count">${category.product_count} шт</div>
            </div>
        `;
    },
    
    cartItem: (item) => {
        return `
            <div class="cart-item" data-product-id="${item.id}">
                <div class="cart-item-image">
                    ${item.image_url ? `<img src="${item.image_url}" alt="${item.name}" style="width:100%;height:100%;object-fit:cover;border-radius:8px;">` : '<i class="ph ph-package"></i>'}
                </div>
                <div class="cart-item-details">
                    <div class="cart-item-name">${item.name}</div>
                    ${item.flavor ? `<div class="cart-item-flavor">${item.flavor}</div>` : ''}
                    <div class="cart-item-controls">
                        <button class="quantity-btn" data-action="decrease" data-product-id="${item.id}">
                            <i class="ph ph-minus"></i>
                        </button>
                        <div class="quantity-value">${item.cart_quantity}</div>
                        <button class="quantity-btn" data-action="increase" data-product-id="${item.id}">
                            <i class="ph ph-plus"></i>
                        </button>
                    </div>
                </div>
                <div class="cart-item-right">
                    <div class="cart-item-price">${utils.formatPrice(item.price * item.cart_quantity)}</div>
                    <button class="btn-remove" data-product-id="${item.id}">
                        <i class="ph ph-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }
};

// ========== Страницы ==========
const pages = {
    home: () => {
        const hotProducts = state.products.filter(p => p.is_hot).slice(0, 6);
        
        return `
            <div class="hero">
                <h1>🔥 HotSpot</h1>
                <p>Лучший выбор качественной продукции</p>
            </div>
            
            <div class="section-title">
                <i class="ph ph-squares-four"></i>
                Категории
            </div>
            <div class="categories-grid">
                ${state.categories.map(cat => components.categoryCard(cat)).join('')}
            </div>
            
            ${hotProducts.length > 0 ? `
                <div class="section-title">
                    <i class="ph ph-fire"></i>
                    Горячие новинки
                </div>
                <div class="products-grid">
                    ${hotProducts.map(p => components.productCard(p)).join('')}
                </div>
            ` : ''}
        `;
    },
    
    category: (categoryId) => {
        const category = state.categories.find(c => c.id == categoryId);
        const products = state.products.filter(p => p.category_id == categoryId);
        
        return `
            <div class="section-title">
                ${category.icon} ${category.name}
            </div>
            ${products.length > 0 ? `
                <div class="products-grid">
                    ${products.map(p => components.productCard(p)).join('')}
                </div>
            ` : `
                <div class="empty-state">
                    <i class="ph ph-package"></i>
                    <p>Нет товаров в этой категории</p>
                </div>
            `}
        `;
    },
    
    search: () => {
        return `
            <div class="search-box">
                <input type="text" class="search-input" id="searchInput" placeholder="Поиск товаров...">
                <button class="search-clear hidden" id="searchClear">
                    <i class="ph ph-x"></i>
                </button>
            </div>
            <div id="searchResults" class="products-grid"></div>
        `;
    },
    
    favorites: () => {
        return state.favorites.length > 0 ? `
            <div class="section-title">
                <i class="ph ph-heart"></i>
                Избранное
            </div>
            <div class="products-grid">
                ${state.favorites.map(p => components.productCard(p)).join('')}
            </div>
        ` : `
            <div class="empty-state">
                <i class="ph ph-heart"></i>
                <p>Избранное пусто</p>
            </div>
        `;
    },
    
    cart: () => {
        if (state.cart.length === 0) {
            return `
                <div class="empty-state">
                    <i class="ph ph-shopping-cart"></i>
                    <p>Корзина пуста</p>
                </div>
            `;
        }
        
        const subtotal = state.cart.reduce((sum, item) => sum + (item.price * item.cart_quantity), 0);
        
        return `
            <div class="section-title">
                <i class="ph ph-shopping-cart"></i>
                Корзина
            </div>
            ${state.cart.map(item => components.cartItem(item)).join('')}
            
            <div class="cart-summary">
                <div class="summary-row">
                    <span>Товары:</span>
                    <span>${utils.formatPrice(subtotal)}</span>
                </div>
                <div class="summary-row">
                    <label class="checkbox-label">
                        <input type="checkbox" id="needDelivery">
                        <span>Нужна доставка (+300₽)</span>
                    </label>
                    <span id="deliveryCost">0₽</span>
                </div>
                ${state.user && state.user.balance > 0 ? `
                    <div class="summary-row">
                        <label class="checkbox-label">
                            <input type="checkbox" id="useBalance">
                            <span>Использовать баланс (${utils.formatPrice(state.user.balance)})</span>
                        </label>
                    </div>
                ` : ''}
                <div class="summary-row total">
                    <span>Итого:</span>
                    <span id="totalAmount">${utils.formatPrice(subtotal)}</span>
                </div>
                <button class="btn-primary btn-full" id="checkoutBtn">
                    Оформить заказ
                </button>
            </div>
        `;
    },
    
    profile: () => {
        // Получить данные из Telegram если доступно
        let displayName = state.user?.first_name || 'Пользователь';
        let displayUsername = state.user?.username || null;
        
        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe) {
            const tgUser = window.Telegram.WebApp.initDataUnsafe.user;
            if (tgUser) {
                displayName = tgUser.first_name || displayName;
                displayUsername = tgUser.username || displayUsername;
            }
        }
        
        const userAvatar = utils.getInitials(displayName);
        const userPhone = state.user?.phone || '';
        
        return `
            <div class="profile-card">
                <div class="profile-avatar">${userAvatar}</div>
                <div class="profile-name">${displayName}</div>
                ${displayUsername ? `<div class="profile-username">@${displayUsername}</div>` : ''}
                <div class="profile-balance">${utils.formatPrice(state.user?.balance || 0)}</div>
            </div>
            
            <div class="profile-phone-section">
                <label class="form-label">Номер телефона</label>
                ${userPhone ? `
                    <div class="current-phone">
                        <i class="ph ph-check-circle"></i>
                        <span>${userPhone}</span>
                    </div>
                ` : ''}
                <div class="phone-input-wrapper">
                    <input type="tel" id="phoneInput" class="form-input" placeholder="+7 (999) 123-45-67" value="${userPhone}">
                    <button class="btn-primary" id="savePhoneBtn">
                        ${userPhone ? 'Изменить' : 'Привязать'}
                    </button>
                </div>
            </div>
            
            <div class="menu-list">
                <button class="menu-item primary" id="applyPromoBtn">
                    <i class="ph ph-ticket"></i>
                    <span>Ввести промокод</span>
                </button>
                <button class="menu-item" id="myOrdersBtn">
                    <i class="ph ph-package"></i>
                    <span>Мои заказы</span>
                </button>
            </div>
        `;
    },
    
    orders: () => {
        // TODO: Реализовать загрузку заказов
        return `
            <div class="section-title">
                <i class="ph ph-package"></i>
                Мои заказы
            </div>
            <div class="empty-state">
                <i class="ph ph-package"></i>
                <p>Заказов пока нет</p>
            </div>
        `;
    }
};

// ========== Навигация ==========
const navigation = {
    goTo: (page, params = {}) => {
        utils.log('Navigation', { page, params });
        
        // Сохранить предыдущую страницу в историю
        if (state.currentPage !== page) {
            state.pageHistory.push(state.currentPage);
        }
        
        state.currentPage = page;
        
        // Обновить навигацию
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });
        
        // Показать/скрыть кнопку назад
        const backBtn = document.getElementById('backBtn');
        if (['home', 'search', 'favorites', 'cart', 'profile'].includes(page)) {
            backBtn.style.display = 'none';
        } else {
            backBtn.style.display = 'flex';
        }
        
        // Рендерить страницу
        const main = document.getElementById('main');
        
        if (page === 'home') {
            main.innerHTML = pages.home();
        } else if (page === 'search') {
            main.innerHTML = pages.search();
            // Инициализировать поиск
            setTimeout(() => {
                const searchInput = document.getElementById('searchInput');
                const searchClear = document.getElementById('searchClear');
                const searchResults = document.getElementById('searchResults');
                
                searchInput.addEventListener('input', async (e) => {
                    const query = e.target.value.trim();
                    searchClear.classList.toggle('hidden', !query);
                    
                    if (query.length >= 2) {
                        const result = await api.searchProducts(query);
                        if (result.success) {
                            searchResults.innerHTML = result.data.map(p => components.productCard(p)).join('');
                        }
                    } else {
                        searchResults.innerHTML = '';
                    }
                });
                
                searchClear.addEventListener('click', () => {
                    searchInput.value = '';
                    searchClear.classList.add('hidden');
                    searchResults.innerHTML = '';
                    searchInput.focus();
                });
            }, 0);
        } else if (page === 'favorites') {
            main.innerHTML = pages.favorites();
        } else if (page === 'cart') {
            main.innerHTML = pages.cart();
            
            // Инициализировать обработчики корзины
            setTimeout(() => {
                const needDelivery = document.getElementById('needDelivery');
                const useBalance = document.getElementById('useBalance');
                const deliveryCost = document.getElementById('deliveryCost');
                const totalAmount = document.getElementById('totalAmount');
                const checkoutBtn = document.getElementById('checkoutBtn');
                
                const updateTotal = () => {
                    const subtotal = state.cart.reduce((sum, item) => sum + (item.price * item.cart_quantity), 0);
                    const delivery = needDelivery?.checked ? 300 : 0;
                    const balance = useBalance?.checked ? Math.min(state.user?.balance || 0, subtotal + delivery) : 0;
                    const total = Math.max(0, subtotal + delivery - balance);
                    
                    if (deliveryCost) deliveryCost.textContent = utils.formatPrice(delivery);
                    if (totalAmount) totalAmount.textContent = utils.formatPrice(total);
                };
                
                needDelivery?.addEventListener('change', updateTotal);
                useBalance?.addEventListener('change', updateTotal);
                
                checkoutBtn?.addEventListener('click', () => {
                    // Открыть модальное окно оформления заказа
                    openCheckoutModal();
                });
            }, 0);
        } else if (page === 'profile') {
            main.innerHTML = pages.profile();
            
            // Инициализировать обработчики профиля
            setTimeout(() => {
                document.getElementById('myOrdersBtn')?.addEventListener('click', () => {
                    navigation.goTo('orders');
                });
                
                document.getElementById('applyPromoBtn')?.addEventListener('click', async () => {
                    const code = prompt('Введите промокод:');
                    if (code) {
                        try {
                            utils.showLoader();
                            const result = await api.applyPromo(code);
                            if (result.success) {
                                utils.showToast(result.message);
                                await loadData();
                                navigation.goTo('profile');
                            } else {
                                utils.showToast(result.error || 'Ошибка', 'error');
                            }
                        } catch (error) {
                            utils.showToast('Ошибка применения промокода', 'error');
                        } finally {
                            utils.hideLoader();
                        }
                    }
                });
                
                document.getElementById('savePhoneBtn')?.addEventListener('click', async () => {
                    const phone = document.getElementById('phoneInput').value.trim();
                    if (!phone) {
                        utils.showToast('Введите номер телефона', 'error');
                        return;
                    }
                    
                    try {
                        utils.showLoader();
                        // Обновить phone через API
                        await api.request('/api/user/phone', {
                            method: 'POST',
                            body: JSON.stringify({ phone })
                        });
                        
                        utils.showToast('Телефон сохранен');
                        await loadUser();
                        navigation.goTo('profile');
                    } catch (error) {
                        utils.showToast('Ошибка сохранения телефона', 'error');
                    } finally {
                        utils.hideLoader();
                    }
                });
            }, 0);
        } else if (page === 'category') {
            main.innerHTML = pages.category(params.categoryId);
        } else if (page === 'orders') {
            main.innerHTML = pages.orders();
        }
        
        // Прокрутить наверх
        window.scrollTo(0, 0);
    },
    
    back: () => {
        if (state.pageHistory.length > 0) {
            const prevPage = state.pageHistory.pop();
            state.currentPage = prevPage;
            navigation.goTo(prevPage);
        }
    }
};

// ========== Модальное окно ==========
const modal = {
    show: (product) => {
        state.selectedProduct = product;
        
        const modalEl = document.getElementById('productModal');
        const modalProductName = document.getElementById('modalProductName');
        const modalProductPrice = document.getElementById('modalProductPrice');
        const modalProductDescription = document.getElementById('modalProductDescription');
        const modalProductDetails = document.getElementById('modalProductDetails');
        const modalProductImage = modalEl.querySelector('.product-modal-image');
        
        modalProductName.textContent = product.name;
        modalProductPrice.textContent = utils.formatPrice(product.price);
        
        // Обновить изображение
        if (product.image_url) {
            modalProductImage.innerHTML = `<img src="${product.image_url}" alt="${product.name}" style="width:100%;height:100%;object-fit:cover;border-radius:12px;">`;
        } else {
            modalProductImage.innerHTML = '<i class="ph ph-package"></i>';
        }
        
        // Генерировать описание
        modalProductDescription.textContent = product.description || 'Качественная продукция для вашего удовольствия.';
        
        // Характеристики
        const details = [];
        if (product.brand) details.push(`<div><strong>Бренд:</strong> ${product.brand}</div>`);
        if (product.strength) details.push(`<div><strong>Крепость:</strong> ${product.strength}</div>`);
        if (product.volume) details.push(`<div><strong>Объем:</strong> ${product.volume}</div>`);
        if (product.flavor) details.push(`<div><strong>Вкус:</strong> ${product.flavor}</div>`);
        if (product.cashback) details.push(`<div><strong>Кешбек:</strong> ${utils.formatPrice(product.cashback)}</div>`);
        details.push(`<div><strong>В наличии:</strong> ${product.quantity} шт</div>`);
        
        modalProductDetails.innerHTML = details.join('');
        
        modalEl.classList.add('active');
    },
    
    hide: () => {
        document.getElementById('productModal').classList.remove('active');
        state.selectedProduct = null;
    }
};

// ========== Обработчики событий ==========
function attachEventHandlers() {
    // Навигация
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            navigation.goTo(item.dataset.page);
        });
    });
    
    // Кнопка назад
    document.getElementById('backBtn').addEventListener('click', () => {
        navigation.back();
    });
    
    // Переключатель темы
    document.getElementById('themeToggle').addEventListener('click', () => {
        const newTheme = state.theme === 'light' ? 'dark' : 'light';
        state.theme = newTheme;
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        const icon = document.querySelector('#themeToggle i');
        icon.className = newTheme === 'light' ? 'ph ph-moon' : 'ph ph-sun';
    });
    
    // Делегирование событий для динамических элементов
    document.getElementById('main').addEventListener('click', async (e) => {
        const target = e.target.closest('[data-product-id], [data-category-id], [data-action]');
        
        if (!target) return;
        
        // Категория
        if (target.classList.contains('category-card')) {
            const categoryId = target.dataset.categoryId;
            navigation.goTo('category', { categoryId });
            return;
        }
        
        // Карточка товара (УБРАНО - не открываем модалку)
        // Карточки маленькие, клик не нужен
        
        // Добавить в корзину
        if (target.classList.contains('add-to-cart')) {
            e.stopPropagation();
            const productId = parseInt(target.dataset.productId);
            
            try {
                utils.showLoader();
                const result = await api.addToCart(productId, 1);
                if (result.success) {
                    utils.showToast('Товар добавлен в корзину');
                    await loadCart();
                }
            } catch (error) {
                utils.showToast('Ошибка добавления в корзину', 'error');
                console.error(error);
            } finally {
                utils.hideLoader();
            }
            return;
        }
        
        // Избранное
        if (target.classList.contains('favorite') || target.closest('.favorite')) {
            e.stopPropagation();
            const btn = target.closest('.favorite');
            const productId = parseInt(btn.dataset.productId);
            
            // Получить координаты для particles
            const rect = btn.getBoundingClientRect();
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            
            try {
                const result = await api.toggleFavorite(productId);
                if (result.success) {
                    // Создать particles
                    utils.createParticles(x, y, result.added);
                    
                    await loadFavorites();
                    
                    // Перерисовать текущую страницу для обновления кнопок
                    const currentPage = state.currentPage;
                    if (currentPage === 'favorites') {
                        navigation.goTo('favorites');
                    } else if (currentPage === 'home') {
                        navigation.goTo('home');
                    } else if (currentPage.startsWith('category')) {
                        const categoryId = state.pageHistory[state.pageHistory.length - 1];
                        if (categoryId && categoryId.indexOf('category') >= 0) {
                            // Перерисовать категорию
                            navigation.goTo(currentPage, { categoryId: state.currentCategoryId });
                        } else {
                            navigation.goTo('home');
                        }
                    }
                    
                    utils.showToast(result.added ? 'Добавлено в избранное ❤️' : 'Удалено из избранного 💔');
                }
            } catch (error) {
                utils.showToast('Ошибка', 'error');
                console.error(error);
            }
            return;
        }
        
        // Управление количеством в корзине
        if (target.classList.contains('quantity-btn')) {
            const action = target.dataset.action;
            const productId = parseInt(target.dataset.productId);
            const item = state.cart.find(i => i.id === productId);
            
            if (!item) return;
            
            let newQuantity = item.cart_quantity;
            if (action === 'increase') {
                newQuantity++;
            } else if (action === 'decrease') {
                newQuantity--;
            }
            
            try {
                if (newQuantity <= 0) {
                    await api.removeFromCart(productId);
                } else {
                    await api.updateCart(productId, newQuantity);
                }
                await loadCart();
                navigation.goTo('cart');
            } catch (error) {
                utils.showToast('Ошибка', 'error');
                console.error(error);
            }
            return;
        }
        
        // Удалить из корзины
        if (target.classList.contains('btn-remove') || target.closest('.btn-remove')) {
            const btn = target.closest('.btn-remove');
            const productId = parseInt(btn.dataset.productId);
            
            try {
                await api.removeFromCart(productId);
                await loadCart();
                navigation.goTo('cart');
                utils.showToast('Товар удален из корзины');
            } catch (error) {
                utils.showToast('Ошибка', 'error');
                console.error(error);
            }
            return;
        }
    });
    
    // Модальное окно
    const productModal = document.getElementById('productModal');
    
    productModal.querySelector('.modal-close').addEventListener('click', () => {
        modal.hide();
    });
    
    productModal.addEventListener('click', (e) => {
        if (e.target === productModal) {
            modal.hide();
        }
    });
    
    document.getElementById('modalAddToCart').addEventListener('click', async () => {
        if (!state.selectedProduct) return;
        
        try {
            utils.showLoader();
            const result = await api.addToCart(state.selectedProduct.id, 1);
            if (result.success) {
                utils.showToast('Товар добавлен в корзину');
                await loadCart();
                modal.hide();
            }
        } catch (error) {
            utils.showToast('Ошибка', 'error');
            console.error(error);
        } finally {
            utils.hideLoader();
        }
    });
}

// ========== Загрузка данных ==========
async function loadCategories() {
    try {
        const result = await api.getCategories();
        if (result.success) {
            state.categories = result.data;
        }
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

async function loadProducts() {
    try {
        const result = await api.getProducts();
        if (result.success) {
            state.products = result.data;
        }
    } catch (error) {
        console.error('Error loading products:', error);
    }
}

async function loadUser() {
    if (!state.telegramUserId) return;
    
    try {
        // Получить данные из Telegram WebApp если доступно
        let telegramUsername = null;
        let telegramFirstName = null;
        
        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe) {
            const tgUser = window.Telegram.WebApp.initDataUnsafe.user;
            if (tgUser) {
                telegramUsername = tgUser.username || null;
                telegramFirstName = tgUser.first_name || null;
            }
        }
        
        const result = await api.getUser(state.telegramUserId);
        if (result.success) {
            state.user = result.data;
            
            // Если есть username из Telegram, но нет в базе - обновить
            if (telegramUsername && !state.user.username) {
                state.user.username = telegramUsername;
            }
            if (telegramFirstName && !state.user.first_name) {
                state.user.first_name = telegramFirstName;
            }
            
            // Обновить UI
            document.getElementById('userBalance').textContent = utils.formatPrice(state.user.balance || 0);
            
            // Показать @username если есть
            const displayName = telegramUsername ? `@${telegramUsername}` 
                              : state.user.username ? `@${state.user.username}`
                              : telegramFirstName ? telegramFirstName
                              : state.user.first_name ? state.user.first_name
                              : 'Пользователь';
            
            document.getElementById('userName').textContent = displayName;
            
            const avatar = document.getElementById('userAvatar');
            avatar.textContent = utils.getInitials(state.user.first_name || state.user.username);
        }
    } catch (error) {
        console.error('Error loading user:', error);
    }
}

async function loadCart() {
    try {
        const result = await api.getCart();
        if (result.success) {
            state.cart = result.data;
            
            // Обновить бейдж
            const badge = document.getElementById('cartBadge');
            const totalItems = state.cart.reduce((sum, item) => sum + item.cart_quantity, 0);
            if (totalItems > 0) {
                badge.textContent = totalItems;
                badge.style.display = 'block';
            } else {
                badge.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading cart:', error);
    }
}

async function loadFavorites() {
    try {
        const result = await api.getFavorites();
        if (result.success) {
            state.favorites = result.data;
            
            // Обновить бейдж
            const badge = document.getElementById('favoritesBadge');
            if (state.favorites.length > 0) {
                badge.textContent = state.favorites.length;
                badge.style.display = 'block';
            } else {
                badge.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading favorites:', error);
    }
}

async function loadData() {
    await Promise.all([
        loadCategories(),
        loadProducts(),
        loadUser(),
        loadCart(),
        loadFavorites()
    ]);
}

// ========== Оформление заказа ==========
function openCheckoutModal() {
    const subtotal = state.cart.reduce((sum, item) => sum + (item.price * item.cart_quantity), 0);
    
    // Открыть модальное окно
    const modal = document.getElementById('checkoutModal');
    modal.classList.add('active');
    
    // Заполнить данные пользователя если есть
    if (state.user) {
        document.getElementById('customerName').value = state.user.first_name || state.user.username || '';
        document.getElementById('customerPhone').value = state.user.phone || '';
    }
    
    // Обновить итоговые суммы
    document.getElementById('checkoutSubtotal').textContent = utils.formatPrice(subtotal);
    document.getElementById('checkoutDelivery').textContent = '0₽';
    document.getElementById('checkoutTotal').textContent = utils.formatPrice(subtotal);
    
    // Обработчик изменения типа доставки
    const deliveryType = document.getElementById('deliveryType');
    const pickupLocationGroup = document.getElementById('pickupLocationGroup');
    const deliveryAddressGroup = document.getElementById('deliveryAddressGroup');
    
    deliveryType.addEventListener('change', () => {
        const isDelivery = deliveryType.value === 'delivery';
        pickupLocationGroup.classList.toggle('hidden', isDelivery);
        deliveryAddressGroup.classList.toggle('hidden', !isDelivery);
        
        const deliveryCost = isDelivery ? 300 : 0;
        document.getElementById('checkoutDelivery').textContent = utils.formatPrice(deliveryCost);
        document.getElementById('checkoutTotal').textContent = utils.formatPrice(subtotal + deliveryCost);
    });
    
    // Закрытие модального окна
    document.getElementById('closeCheckout').onclick = () => {
        modal.classList.remove('active');
    };
    
    modal.onclick = (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    };
    
    // Обработчик отправки формы
    document.getElementById('submitOrder').onclick = async (e) => {
        e.preventDefault();
        
        const name = document.getElementById('customerName').value.trim();
        const phone = document.getElementById('customerPhone').value.trim();
        const deliveryTypeVal = document.getElementById('deliveryType').value;
        const paymentMethod = document.getElementById('paymentMethod').value;
        
        if (!name || !phone) {
            utils.showToast('Заполните все обязательные поля', 'error');
            return;
        }
        
        const orderData = {
            customer_name: name,
            customer_phone: phone,
            delivery_type: deliveryTypeVal,
            payment_method: paymentMethod,
            use_balance: false
        };
        
        if (deliveryTypeVal === 'pickup') {
            orderData.pickup_location = document.getElementById('pickupLocation').value;
        } else {
            const address = document.getElementById('deliveryAddress').value.trim();
            if (!address) {
                utils.showToast('Укажите адрес доставки', 'error');
                return;
            }
            orderData.delivery_address = address;
        }
        
        try {
            utils.showLoader();
            
            const result = await api.createOrder(orderData);
            
            if (result.success) {
                // Сохранить телефон если не был сохранен ранее
                if (phone && (!state.user?.phone || state.user.phone !== phone)) {
                    try {
                        await api.request('/api/user/phone', {
                            method: 'POST',
                            body: JSON.stringify({ phone })
                        });
                    } catch (error) {
                        console.error('Error saving phone:', error);
                    }
                }
                
                // Закрыть модальное окно
                modal.classList.remove('active');
                
                // Сформировать сообщение для менеджера
                const orderMessage = formatOrderMessage(result.order_id, orderData, subtotal);
                
                // Редирект в Telegram к менеджеру
                const managerUsername = 'hotspotovich67'; // Из config
                const telegramUrl = `https://t.me/${managerUsername}?text=${encodeURIComponent(orderMessage)}`;
                
                // Открыть Telegram
                if (window.Telegram && window.Telegram.WebApp) {
                    window.Telegram.WebApp.openTelegramLink(telegramUrl);
                } else {
                    window.open(telegramUrl, '_blank');
                }
                
                // Обновить данные
                await loadData();
                
                // Показать сообщение
                utils.showToast(`Заказ №${result.order_id} создан! Переходим к менеджеру...`);
                
                // Перейти на главную через 2 секунды
                setTimeout(() => {
                    navigation.goTo('home');
                }, 2000);
            }
        } catch (error) {
            utils.showToast('Ошибка создания заказа', 'error');
            console.error(error);
        } finally {
            utils.hideLoader();
        }
    };
}

function formatOrderMessage(orderId, orderData, subtotal) {
    const deliveryCost = orderData.delivery_type === 'delivery' ? 300 : 0;
    const total = subtotal + deliveryCost;
    
    let message = `🔥 ЗАКАЗ №${orderId}\n\n`;
    
    // Состав заказа
    message += '📦 Состав заказа:\n';
    state.cart.forEach((item, index) => {
        message += `${index + 1}. ${item.name}`;
        if (item.flavor) message += ` (${item.flavor})`;
        message += ` x${item.cart_quantity} = ${utils.formatPrice(item.price * item.cart_quantity)}\n`;
    });
    message += '\n';
    
    // Данные клиента
    message += `👤 Клиент: ${orderData.customer_name}\n`;
    message += `📞 Телефон: ${orderData.customer_phone}\n\n`;
    
    // Доставка
    if (orderData.delivery_type === 'pickup') {
        message += `📍 Самовывоз: ${orderData.pickup_location}\n`;
    } else {
        message += `🚚 Доставка: ${orderData.delivery_address}\n`;
        message += `Стоимость доставки: ${utils.formatPrice(deliveryCost)}\n`;
    }
    message += '\n';
    
    // Оплата
    const paymentMethods = {
        'sbp_online': 'СБП (онлайн)',
        'sbp_pickup': 'СБП (при получении)',
        'cash': 'Наличные',
        'balance': 'Баланс'
    };
    message += `💳 Способ оплаты: ${paymentMethods[orderData.payment_method]}\n\n`;
    
    // Итого
    message += `💰 ИТОГО: ${utils.formatPrice(total)}`;
    
    return message;
}

// ========== Инициализация ==========
async function init() {
    utils.log('Initializing app...');
    
    // Показать загрузчик
    utils.showLoader();
    
    // Определить Telegram User ID
    if (window.Telegram && window.Telegram.WebApp) {
        const tg = window.Telegram.WebApp;
        tg.ready();
        
        if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
            state.telegramUserId = tg.initDataUnsafe.user.id;
            utils.log('Telegram User ID:', state.telegramUserId);
        }
        
        // Настроить тему из Telegram
        if (tg.colorScheme) {
            state.theme = tg.colorScheme;
            document.documentElement.setAttribute('data-theme', state.theme);
        }
    }
    
    // Если нет Telegram ID, попробовать из URL или localStorage
    if (!state.telegramUserId) {
        const urlParams = new URLSearchParams(window.location.search);
        state.telegramUserId = urlParams.get('user_id') || localStorage.getItem('telegram_user_id') || null;
    }
    
    // БЛОКИРОВКА БЕЗ АВТОРИЗАЦИИ
    // Если нет Telegram ID - просто показываем загрузчик и не инициализируем
    if (!state.telegramUserId) {
        utils.log('No Telegram User ID found - waiting for authorization...');
        // Показать сообщение в загрузчике
        const loaderEl = document.getElementById('loader');
        const loaderText = loaderEl.querySelector('p');
        if (loaderText) {
            loaderText.textContent = 'Ожидание авторизации...';
        }
        // Оставляем загрузчик видимым
        return;
    }
    
    // Сохранить в localStorage для следующего раза
    localStorage.setItem('telegram_user_id', state.telegramUserId);
    
    // Восстановить тему из localStorage
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        state.theme = savedTheme;
        document.documentElement.setAttribute('data-theme', savedTheme);
        
        const icon = document.querySelector('#themeToggle i');
        icon.className = savedTheme === 'light' ? 'ph ph-moon' : 'ph ph-sun';
    }
    
    // Прикрепить обработчики
    attachEventHandlers();
    
    // Загрузить данные
    await loadData();
    
    // Показать главную страницу
    navigation.goTo('home');
    
    // Скрыть загрузчик
    utils.hideLoader();
    
    utils.log('App initialized successfully!');
}

// Запуск при загрузке страницы
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

