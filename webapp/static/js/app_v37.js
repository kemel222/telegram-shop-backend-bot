/**
 * HotSpot Shop - Web Application
 * Version: 37.0 - Full Redesign
 */

// ======================
// CONFIGURATION
// ======================
const CONFIG = {
    API_BASE: window.location.origin,
    DEBUG: true,
    DELIVERY_COST: 300,
    FREE_DELIVERY_FROM: 3000,
    TOAST_DURATION: 3000,
    MANAGER_TELEGRAM: '@hotspotovich67',
    REQUIRE_AUTH: true // Не пускать без авторизации
};

// ======================
// STATE MANAGEMENT
// ======================
const state = {
    user: null,
    telegramUserId: null,
    telegramUserData: null,  // Данные пользователя из Telegram WebApp
    categories: [],
    products: [],
    cart: [],
    autoDiscounts: null,  // Автоматические скидки для корзины
    favorites: [],
    orders: [],
    currentPage: 'home',
    pageHistory: [],
    selectedProduct: null,
    selectedVariant: null,
    currentCategoryId: null,
    theme: 'light'
};

// ======================
// UTILITY FUNCTIONS
// ======================
const utils = {
    log(message, data = '') {
        if (CONFIG.DEBUG) console.log(`[HotSpot] ${message}`, data);
    },

    showLoader() {
        const loader = document.getElementById('loader');
        if (loader) loader.classList.remove('hidden');
    },

    hideLoader() {
        const loader = document.getElementById('loader');
        if (loader) loader.classList.add('hidden');
    },

    showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        if (!toast) return;
        
        toast.textContent = message;
        toast.className = `toast show ${type}`;
        
        setTimeout(() => {
            toast.className = 'toast';
        }, CONFIG.TOAST_DURATION);
    },

    formatPrice(price) {
        const num = parseFloat(price);
        return isNaN(num) ? '0₽' : `${Math.round(num)}₽`;
    },

    getInitials(name) {
        return name ? name.charAt(0).toUpperCase() : 'П';
    },

    transliterate(text) {
        const map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        };
        return text.toLowerCase().split('').map(c => map[c] || c).join('');
    },

    // Расстояние Левенштейна для поиска опечаток
    levenshteinDistance(str1, str2) {
        const matrix = [];
        
        for (let i = 0; i <= str2.length; i++) {
            matrix[i] = [i];
        }
        
        for (let j = 0; j <= str1.length; j++) {
            matrix[0][j] = j;
        }
        
        for (let i = 1; i <= str2.length; i++) {
            for (let j = 1; j <= str1.length; j++) {
                if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1,
                        matrix[i][j - 1] + 1,
                        matrix[i - 1][j] + 1
                    );
                }
            }
        }
        
        return matrix[str2.length][str1.length];
    },

    searchMatch(text, query) {
        if (!text || !query) return false;
        
        const textLower = text.toLowerCase().trim();
        const queryLower = query.toLowerCase().trim();
        const textTranslit = this.transliterate(text);
        const queryTranslit = this.transliterate(query);
        
        // Расширенные варианты написания брендов и товаров
        const brandVariants = {
            // Бренды одноразок
            'catswill': ['кэтсвил', 'катсвил', 'кетсвил', 'кэтсвилл', 'катсвилл', 'кетсвилл', 'кат', 'кет', 'кэт', 'катс', 'кэтс', 'catsw', 'ketswill', 'кэ', 'ка', 'ке'],
            'кэтсвил': ['catswill', 'catswil', 'кат', 'кет', 'катс', 'кэ'],
            'кэтсвилл': ['catswill', 'catswil', 'кат', 'кет', 'катс', 'кэ'],
            'катсвил': ['catswill', 'catswil', 'кат', 'кет', 'катс', 'ка'],
            'катсвилл': ['catswill', 'catswil', 'кат', 'кет', 'катс', 'ка'],
            'кетсвил': ['catswill', 'catswil', 'кат', 'кет', 'катс', 'ке'],
            'кетсвилл': ['catswill', 'catswil', 'кат', 'кет', 'катс', 'ке'],
            'geek': ['гик', 'гек', 'геек', 'гик бар', 'гек бар', 'geekbar', 'гикбар', 'гекбар', 'геекбар', 'бар', 'bar', 'ге', 'ги'],
            'гик': ['geek', 'geek bar', 'geekbar', 'bar', 'бар', 'ги'],
            'гек': ['geek', 'geek bar', 'geekbar', 'bar', 'бар', 'ге'],
            'bar': ['бар', 'geek', 'гик', 'гек'],
            'бар': ['bar', 'geek', 'гик', 'гек'],
            'waka': ['вака', 'вска', 'вака смо', 'вака соло', 'waxa', 'вакка', 'waka sopro', 'sopro', 'vaka', 'ва', 'ваканда'],
            'вака': ['waka', 'vaka', 'waxa', 'ва', 'ваканда'],
            'вска': ['waka', 'vaka', 'ва'],
            'ваканда': ['waka', 'вака', 'ва'],
            'sopro': ['сопро', 'co pro', 'со про'],
            'elfbar': ['эльф', 'элф', 'елф', 'ельф бар', 'элфбар', 'elf', 'эльфбар', 'эл', 'ел'],
            'эльф': ['elfbar', 'elf bar', 'elf', 'эл'],
            'элф': ['elfbar', 'elf bar', 'elf', 'эл'],
            'елф': ['elfbar', 'elf bar', 'elf', 'ел'],
            
            // Pod системы (обработка буквы X)
            'aegis': ['аегис', 'аегус', 'эгис', 'эгус', 'аеджис', 'aegus', 'аегиз', 'ае', 'аe'],
            'аегис': ['aegis', 'egis', 'ае'],
            'аегус': ['aegis', 'egis', 'ае'],
            'xros': ['хрос', 'кросс', 'cross', 'хроз', 'кроз', 'икрос', 'хр', 'кр', 'х', 'xpo', 'хpo'],
            'хрос': ['xros', 'cross', 'хр', 'х'],
            'кросс': ['xros', 'cross', 'кр'],
            'vaporesso': ['вапорессо', 'вапоресо', 'вапореско', 'вапор', 'vapor', 'вапо', 'ва', 'vap'],
            'вапорессо': ['vaporesso', 'vapor', 'вап', 'ва'],
            'вапор': ['vaporesso', 'vapor', 'вап', 'ва'],
            'knight': ['кнайт', 'найт', 'knait', 'knight80', 'кнайт80', 'кн', 'kn'],
            'кнайт': ['knight', 'knait', 'кн'],
            
            // Жидкости
            'mad': ['мэд', 'мед', 'мад', 'мод', 'мид', 'маd', 'ме', 'мэ', 'мо', 'ми'],
            'мэд': ['mad', 'мед', 'мод', 'мид', 'мэ'],
            'мед': ['mad', 'мэд', 'мод', 'мид', 'ме'],
            'мод': ['mad', 'мэд', 'мед', 'мид', 'мо'],
            'мид': ['mad', 'мэд', 'мед', 'мод', 'ми'],
            'анархия': ['anarchy', 'anarchia', 'аннархия', 'анархя', 'ан', 'ana'],
            'anarchy': ['анархия', 'anarchia', 'ан'],
            'монархия': ['monarchy', 'monarchia', 'маонархия', 'мон'],
            'грех': ['greh', 'гр', 'g'],
            'самоубийца': ['samoubiica', 'samoubica', 'samoubiyca', 'самауб', 'самуб', 'саубийца', 'сам', 'са'],
            'злая': ['zlaya', 'злоя', 'зля', 'зл'],
            'злой': ['zlaya', 'злоя', 'зл'],
            'ангри': ['энгри', 'angry', 'ангри вейп', 'энгри вейп', 'ангри вэйп', 'энгри вэйп', 'ang', 'энг'],
            'энгри': ['ангри', 'angry', 'энгри вейп', 'ангри вэйп', 'энг', 'ang'],
            'angry': ['ангри', 'энгри', 'ang', 'энг'],
            'монашка': ['monashka', 'манашка', 'мон', 'мо'],
            
            // Pasito
            'pasito': ['пасито', 'пасито 2', 'пасик', 'пасито2', 'паситос', 'пас', 'па'],
            'пасито': ['pasito', 'пасито 2', 'пасик', 'пасито2', 'паситос', 'пас', 'па'],
            'пасито2': ['pasito', 'пасито', 'пасито 2', 'пасик', 'паситос'],
            'пасик': ['pasito', 'пасито', 'пасито 2', 'пасито2', 'паситос'],
            'паситос': ['pasito', 'пасито', 'пасито 2', 'пасик', 'пасито2'],
            
            // Общие
            'hotspot': ['хотспот', 'хот спот', 'хот', 'хотспод', 'хо', 'хотсп', 'хотс', 'хот спот'],
            'хотспот': ['hotspot', 'hot spot', 'хот', 'хо', 'хотсп', 'хотс'],
            'хот': ['hotspot', 'hot', 'хотспот', 'хо'],
            'хо': ['hotspot', 'хот', 'хотспот'],
            'хотсп': ['hotspot', 'хотспот', 'хот'],
            'хотс': ['hotspot', 'хотспот', 'хот'],
            'isterika': ['истерика', 'истeрика', 'истерека', 'isterica', 'ис', 'ист'],
            'истерика': ['isterika', 'isterica', 'ис', 'ист'],
            'podonki': ['подонки', 'падонки', 'подонкi', 'podonky', 'по', 'под'],
            'подонки': ['podonki', 'padonki', 'по', 'под'],
            
            // Типы товаров
            'одноразка': ['одноразовая', 'однораз', 'одноразки', 'одноразовые', 'од', 'одн'],
            'картридж': ['картриж', 'картридждж', 'картрижд', 'карт', 'ка'],
            'испаритель': ['испарител', 'испоритель', 'испаратель', 'ис', 'исп'],
            'жижа': ['жидкость', 'жижка', 'жижи', 'жыжа', 'жи'],
            'жидкость': ['жижа', 'жидкосьть', 'жи'],
            'под': ['pod', 'пот', 'pood', 'по'],
            'pod': ['под', 'пот', 'по']
        };
        
        // 1. Точное совпадение (базовое)
        if (textLower.includes(queryLower)) return true;
        
        // 2. Транслитерация
        if (textTranslit.includes(queryLower) || 
            textLower.includes(queryTranslit) ||
            textTranslit.includes(queryTranslit)) {
            return true;
        }
        
        // 3. Обработка буквы X (икс/х/хэ)
        const queryWithX = queryLower.replace(/x/g, 'х').replace(/х/g, 'x');
        const textWithX = textLower.replace(/x/g, 'х').replace(/х/g, 'x');
        if (textLower.includes(queryWithX) || textWithX.includes(queryLower)) {
            return true;
        }
        
        // 4. Проверка вариантов брендов
        for (const [key, variants] of Object.entries(brandVariants)) {
            // Поиск по ключу
            if (queryLower === key || queryLower.startsWith(key)) {
                for (const variant of variants) {
                    if (textLower.includes(variant) || textLower.startsWith(variant)) return true;
                }
            }
            
            // Поиск по вариантам
            if (textLower === key || textLower.startsWith(key)) {
                for (const variant of variants) {
                    if (queryLower === variant || queryLower.startsWith(variant)) return true;
                }
            }
            
            // Обычное включение
            if (queryLower.includes(key)) {
                for (const variant of variants) {
                    if (textLower.includes(variant)) return true;
                }
            }
            
            if (textLower.includes(key)) {
                for (const variant of variants) {
                    if (queryLower.includes(variant)) return true;
                }
            }
        }
        
        // 5. Проверка по словам (для запросов из нескольких слов)
        const queryWords = queryLower.split(/\s+/);
        const textWords = textLower.split(/\s+/);
        
        if (queryWords.length > 1) {
            const matchedWords = queryWords.filter(qWord => 
                textWords.some(tWord => 
                    tWord.includes(qWord) || 
                    qWord.includes(tWord) ||
                    tWord.startsWith(qWord) ||
                    qWord.startsWith(tWord) ||
                    this.levenshteinDistance(qWord, tWord) <= 1
                )
            );
            
            if (matchedWords.length >= Math.ceil(queryWords.length * 0.7)) {
                        return true;
                    }
                }
        
        // 6. Опечатки - расстояние Левенштейна
        if (queryLower.length >= 3 && queryLower.length <= 15) {
            const queryClean = queryLower.replace(/\s+/g, '');
            
            // Проверяем каждое слово в тексте
            for (const word of textWords) {
                if (word.length >= 3 && 
                    Math.abs(word.length - queryClean.length) <= 3) {
                    const distance = this.levenshteinDistance(queryClean, word);
                    const maxDistance = Math.max(1, Math.floor(queryClean.length / 3)); // До 33% опечаток
                    
                    if (distance <= maxDistance && distance <= 2) {
                        return true;
                    }
                }
            }
        }
        
        // 7. Частичное совпадение в начале слова (с ПЕРВОЙ буквы!)
        for (const word of textWords) {
            // Совпадение с начала слова
            if (word.startsWith(queryLower) && queryLower.length >= 1) {
                return true;
            }
            
            // Запрос начинается с части слова
            if (queryLower.startsWith(word) && word.length >= 2) {
                return true;
            }
        }
        
        // 8. Проверка с начала текста (для очень коротких запросов 1-2 буквы)
        if (queryLower.length <= 2) {
            if (textLower.startsWith(queryLower)) {
                return true;
            }
        }
        
        return false;
    },

    getBrandGroup(brand) {
        if (!brand) return 'Без бренда';
        if (brand.toLowerCase().includes('грех')) return 'ГРЕХ';
        return brand.split(/[\s&]+/)[0].trim() || brand;
    },

    showBannedMessage() {
        const appEl = document.getElementById('app');
        if (!appEl) return;
        
        appEl.innerHTML = `
            <div class="banned-screen">
                <div class="banned-icon">🚫</div>
                <h1 class="banned-title">Доступ ограничен</h1>
                <p class="banned-text">
                    Ваш аккаунт заблокирован.<br>
                    Обратитесь в поддержку для уточнения деталей.
                </p>
                <a href="https://t.me/hotspotovich67" class="banned-support-btn">
                    💬 Связаться с поддержкой
                </a>
            </div>
        `;
    }
};

// ======================
// API SERVICE
// ======================
const api = {
    async request(endpoint, options = {}) {
        try {
            const url = `${CONFIG.API_BASE}${endpoint}`;
            utils.log(`API Request: ${endpoint}`, options);
            
            // Добавить X-Telegram-User-Id заголовок если есть telegramUserId
            const headers = {
                'Content-Type': 'application/json',
                ...options.headers
            };
            
            if (state.telegramUserId) {
                headers['X-Telegram-User-Id'] = state.telegramUserId.toString();
            }
            
            const response = await fetch(url, {
                headers: headers,
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            utils.log(`API Response: ${endpoint}`, data);
            return data;
        } catch (error) {
            utils.log(`API Error: ${endpoint}`, error);
            throw error;
        }
    },

    getUser(telegramUserId) {
        return this.request(`/api/user/${telegramUserId}`);
    },

    getCategories() {
        return this.request('/api/categories');
    },

    getProducts() {
        return this.request('/api/products');
    },

    getOrders() {
        return this.request('/api/orders');
    },

    createOrder(orderData) {
        return this.request('/api/orders', {
            method: 'POST',
            body: JSON.stringify(orderData)
        });
    },

    // Метод для избранного
    async toggleFavorite(telegramUserId, variantId) {
        try {
            // Сначала проверяем, есть ли пользователь
            const userData = await this.getUser(telegramUserId);
            if (!userData || !userData.user) {
                throw new Error('User not found');
            }
            
            return this.request('/api/favorites/toggle', {
                method: 'POST',
                body: JSON.stringify({ 
                    product_id: variantId  // Бэкенд ожидает product_id
                })
            });
        } catch (error) {
            utils.log('Toggle favorite error', error);
            throw error;
        }
    },

    applyPromocode(code) {
        return this.request('/api/promocode/apply', {
            method: 'POST',
            body: JSON.stringify({ code: code })
        });
    },
    
    // Получить активные скидки
    // Регистрация нового пользователя
    registerUser(userData) {
        return this.request('/api/user/register', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    },
    
    // Методы для работы с корзиной
    getCart() {
        return this.request('/api/cart');
    },
    
    addToCart(variantId, quantity = 1) {
        return this.request('/api/cart/add', {
            method: 'POST',
            body: JSON.stringify({ variant_id: variantId, quantity })
        });
    },
    
    updateCartItem(variantId, quantity) {
        return this.request('/api/cart/update', {
            method: 'POST',
            body: JSON.stringify({ variant_id: variantId, quantity })
        });
    },
    
    removeFromCart(variantId) {
        return this.request('/api/cart/remove', {
            method: 'POST',
            body: JSON.stringify({ variant_id: variantId })
        });
    },
    
    syncCart(items) {
        return this.request('/api/cart/sync', {
            method: 'POST',
            body: JSON.stringify({ 
                items: items.map(item => ({
                    variant_id: item.variantId,
                    quantity: item.quantity
                }))
            })
        });
    }
};

// ======================
// DATA MANAGEMENT
// ======================
const dataManager = {
    async loadAll() {
        utils.showLoader();
        
        try {
            // СНАЧАЛА загружаем только пользователя для проверки бана
            let userNotFound = false;
            
            const userData = await api.getUser(state.telegramUserId).catch(err => {
                    utils.log('User load error (will use defaults)', err);
                    // Запоминаем что пользователь не найден
                    if (err.message.includes('404')) {
                        userNotFound = true;
                    }
                    return { user: null, favorites: [], error: true };
            });

            // Если пользователь не найден - пытаемся зарегистрировать
            if (userNotFound && state.telegramUserData) {
                utils.log('User not found, attempting auto-registration...');
                
                try {
                    // Парсим данные из Telegram WebApp
                    const newUserData = {
                        telegram_user_id: state.telegramUserId,
                        first_name: state.telegramUserData.first_name || 'Пользователь',
                        last_name: state.telegramUserData.last_name || null,
                        username: state.telegramUserData.username || null,
                        language_code: state.telegramUserData.language_code || 'ru',
                        is_premium: state.telegramUserData.is_premium || false
                    };
                    
                    utils.log('Registering new user:', newUserData);
                    
                    // Отправляем запрос на регистрацию
                    const registerResult = await api.registerUser(newUserData);
                    
                    if (registerResult.success && registerResult.user) {
                        // Регистрация успешна ИЛИ пользователь уже существует
                        const message = registerResult.message === 'User already registered' 
                            ? '✅ С возвращением!' 
                            : '✅ Добро пожаловать! Вы успешно зарегистрированы';
                        
                        utils.showToast(message);
                        utils.log('User data loaded:', registerResult);
                        
                        // Устанавливаем данные пользователя
                        state.user = registerResult.user;
                        userNotFound = false;
                    } else {
                        utils.log('Registration failed:', registerResult);
                        utils.showToast('Ошибка регистрации. Обратитесь к администратору', 'error');
                    }
                } catch (registerError) {
                    utils.log('Registration error:', registerError);
                    utils.showToast('Не удалось зарегистрировать пользователя', 'error');
                }
            }

            // Если требуется авторизация и пользователь всё ещё не найден
            if (CONFIG.REQUIRE_AUTH && (userNotFound || (userData.error && !state.user))) {
                state.user = null;
            } else if (!state.user) {
                // Устанавливаем данные с безопасными значениями по умолчанию
                state.user = userData.user || {
                    id: state.telegramUserId,
                    telegram_user_id: state.telegramUserId,
                    first_name: 'Пользователь',
                    username: null,
                    balance: 0,
                    phone: null,
                    is_banned: 0
                };
            }
            
            // ⚠️ КРИТИЧЕСКАЯ ПРОВЕРКА БАНА - ПЕРЕД ЗАГРУЗКОЙ ОСТАЛЬНЫХ ДАННЫХ
            utils.log('🔍 Checking ban status:', {
                user: state.user,
                is_banned: state.user?.is_banned,
                type: typeof state.user?.is_banned
            });
            
            if (state.user && (state.user.is_banned === 1 || state.user.is_banned === true)) {
                utils.log('🚫 USER IS BANNED - Showing ban screen');
                document.body.classList.add('user-banned');
                utils.hideLoader();
                utils.showBannedMessage();
                return; // Полностью прекратить загрузку данных
            } else {
                utils.log('✅ User is NOT banned - Continue loading');
                document.body.classList.remove('user-banned');
            }
            
            // Пользователь НЕ забанен - загружаем остальные данные
            const [categories, products, orders] = await Promise.all([
                api.getCategories().catch(err => {
                    utils.log('Categories load error', err);
                    return { success: false, data: [] };
                }),
                api.getProducts().catch(err => {
                    utils.log('Products load error', err);
                    return { success: false, data: [] };
                }),
                api.getOrders().catch(err => {
                    utils.log('Orders load error (will use empty)', err);
                    return { orders: [], data: [] };
                })
            ]);
            
            // Обновить username если он изменился в Telegram
            if (state.user && state.telegramUserData && state.telegramUserData.username) {
                const currentUsername = state.user.username;
                const newUsername = state.telegramUserData.username;
                
                // Если username отличается или отсутствовал - обновляем
                if (currentUsername !== newUsername) {
                    utils.log('Updating username:', { old: currentUsername, new: newUsername });
                    
                    // Обновляем локально
                    state.user.username = newUsername;
                    
                    // Отправляем обновление на сервер (без await чтобы не блокировать загрузку)
                    api.request(`/api/admin/clients/${state.user.id}`, {
                        method: 'PATCH',
                        body: JSON.stringify({ 
                            name: state.telegramUserData.first_name || state.user.first_name,
                            phone: state.user.phone 
                        })
                    }).catch(err => {
                        utils.log('Failed to update username on server:', err);
                    });
                    
                    // Также обновляем через специальный endpoint если он есть
                    fetch(`${CONFIG.API_BASE}/api/user/${state.telegramUserId}/update-username`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Telegram-User-Id': state.telegramUserId.toString()
                        },
                        body: JSON.stringify({ username: newUsername })
                    }).catch(err => {
                        utils.log('Failed to update username via special endpoint:', err);
                    });
                }
            }
            
            // Обработка разных форматов ответов API
            state.categories = categories.data || categories.categories || [];
            state.products = products.data || products.products || [];
            state.orders = orders.data || orders.orders || [];
            state.favorites = userData.favorites || [];
            
            this.loadCart();
            this.updateUI();
            
            utils.log('Data loaded successfully', {
                user: !!state.user,
                categories: state.categories.length,
                products: state.products.length,
                orders: state.orders.length,
                favorites: state.favorites.length
            });
        } catch (error) {
            utils.log('Critical load error', error);
            
            // Устанавливаем минимальные данные для работы
            state.user = state.user || {
                id: state.telegramUserId,
                telegram_user_id: state.telegramUserId,
                first_name: 'Пользователь',
                username: null,
                balance: 0,
                phone: null
            };
            state.categories = state.categories || [];
            state.products = state.products || [];
            state.orders = state.orders || [];
            state.favorites = state.favorites || [];
            
            this.loadCart();
            this.updateUI();
        } finally {
            utils.hideLoader();
        }
    },

    async loadCart() {
        // Сначала пытаемся загрузить с сервера
        try {
            const result = await api.getCart();
            console.log('[HotSpot] Cart API response:', result);
            
            if (result.success) {
                // Сохраняем информацию об автоматических скидках (даже если корзина пустая)
                state.autoDiscounts = result.discount_info || null;
                
                console.log('[HotSpot] Auto discounts:', state.autoDiscounts);
                
                if (result.data && result.data.length > 0) {
                // Преобразуем данные с сервера в формат фронтенда
                state.cart = result.data.map(item => ({
                    variantId: item.variant_id,
                        productId: item.product_id || item.id,
                    name: item.name,
                    brand: item.brand,
                    flavor: item.flavor,
                        price: item.price || item.base_price || 0, // Цена из товара
                    image: item.image_url,
                    quantity: item.cart_quantity || item.quantity,
                    maxQuantity: item.stock_quantity
                }));
                
                // Сохраняем локально как кэш
                localStorage.setItem('cart', JSON.stringify(state.cart));
                this.updateCartBadge();
                    console.log('[HotSpot] Корзина загружена с сервера:', state.cart);
                    return;
                } else {
                    // Корзина пустая на сервере - очищаем локальную
                    state.cart = [];
                    state.autoDiscounts = null;
                    localStorage.removeItem('cart');
                    this.updateCartBadge();
                return;
                }
            }
        } catch (error) {
            console.log('[HotSpot] Не удалось загрузить корзину с сервера:', error);
        }
        
        // Если не получилось загрузить с сервера - используем localStorage
        const saved = localStorage.getItem('cart');
        state.cart = saved ? JSON.parse(saved) : [];
        
        // Обновляем цены в корзине из актуальных данных товаров
        state.cart = state.cart.map(item => {
            const product = state.products.find(p => p.id === item.productId);
            if (product) {
                // Обновляем цену из товара
                const price = product.price || product.base_price || item.price || 0;
                return {
                    ...item,
                    price: price
                };
            }
            return item;
        }).filter(item => item.price > 0); // Убираем товары без цены
        
        this.updateCartBadge();
        
        // Синхронизируем локальную корзину с сервером
        if (state.cart.length > 0) {
            this.syncCartToServer();
        }
    },

    saveCart() {
        localStorage.setItem('cart', JSON.stringify(state.cart));
        this.updateCartBadge();
    },
    
    async syncCartToServer() {
        // Синхронизация локальной корзины с сервером (например, при первом заходе)
        // Полная замена серверной корзины на локальную
        try {
            if (state.cart.length === 0) {
                console.log('Корзина пустая, синхронизация не требуется');
                return;
            }
            
            console.log('Синхронизация корзины с сервером...', state.cart);
            await api.syncCart(state.cart);
            console.log('Корзина успешно синхронизирована');
        } catch (error) {
            console.error('Ошибка синхронизации корзины:', error);
        }
    },

    updateCartBadge() {
        const badge = document.querySelector('.cart-badge');
        if (!badge) return;
        
        const total = state.cart.reduce((sum, item) => sum + item.quantity, 0);
        badge.textContent = total;
        badge.style.display = total > 0 ? 'flex' : 'none';
    },

    updateUI() {
        const avatar = document.getElementById('userAvatar');
        const fullName = document.getElementById('userFullName');
        const balance = document.getElementById('userBalance');
        const username = document.getElementById('userUsername');

        if (state.user) {
            // Аватарка: пытаемся получить фото из Telegram
            if (avatar) {
                const photoUrl = state.telegramUserData?.photo_url;
                if (photoUrl) {
                    // Заменяем текстовый аватар на фото
                    avatar.style.backgroundImage = `url(${photoUrl})`;
                    avatar.style.backgroundSize = 'cover';
                    avatar.style.backgroundPosition = 'center';
                    avatar.textContent = ''; // Убираем инициалы
                } else {
                    // Если фото нет - показываем инициалы
                    avatar.style.backgroundImage = 'none';
                    avatar.textContent = utils.getInitials(state.user.first_name || 'П');
                }
            }
            
            if (fullName) fullName.textContent = state.user.first_name || 'Пользователь';
            if (balance) balance.textContent = utils.formatPrice(state.user.balance || 0);
            if (username) username.textContent = state.user.username ? `@${state.user.username}` : '';
        }
    }
};

// ======================
// CART MANAGEMENT
// ======================
const cart = {
    async add(variant, product) {
        // Цена берется из товара, а не из варианта
        const price = product.price || product.base_price || 0;
        
        utils.log('Adding to cart:', {
            product: product.name,
            variant: variant.flavor,
            productPrice: product.price,
            basePrice: product.base_price,
            finalPrice: price
        });
        
        const existing = state.cart.find(item => item.variantId === variant.id);
        
        if (existing) {
            if (existing.quantity < variant.quantity) {
                existing.quantity++;
                // Обновляем цену на случай если она изменилась
                existing.price = price;
                utils.showToast('Товар добавлен в корзину');
            } else {
                utils.showToast('Недостаточно товара на складе', 'error');
                return;
            }
        } else {
            state.cart.push({
                variantId: variant.id,
                productId: product.id,
                name: product.name,
                brand: product.brand,
                flavor: variant.flavor,
                price: price,
                image: product.image_url,
                quantity: 1,
                maxQuantity: variant.quantity
            });
            utils.showToast('Товар добавлен в корзину');
        }
        
        // Синхронизируем с сервером
        try {
            await api.addToCart(variant.id, 1);
            // Перезагружаем корзину с сервера, чтобы получить обновлённые скидки
            await dataManager.loadCart();
        } catch (error) {
            console.error('Ошибка синхронизации корзины с сервером:', error);
            dataManager.saveCart();
        }
        
        if (state.currentPage === 'cart') {
            navigation.render();
        }
    },

    async remove(variantId) {
        state.cart = state.cart.filter(item => item.variantId !== variantId);
        
        // Синхронизируем с сервером
        try {
            await api.removeFromCart(variantId);
            // Перезагружаем корзину с сервера, чтобы получить обновлённые скидки
            await dataManager.loadCart();
        } catch (error) {
            console.error('Ошибка синхронизации корзины с сервером:', error);
            dataManager.saveCart();
        }
        
        navigation.render();
        utils.showToast('Товар удалён из корзины');
    },

    async updateQuantity(variantId, delta) {
        const item = state.cart.find(i => i.variantId === variantId);
        if (!item) return;

        const newQuantity = item.quantity + delta;
        
        if (newQuantity <= 0) {
            await this.remove(variantId);
        } else if (newQuantity <= item.maxQuantity) {
            item.quantity = newQuantity;
            
            // Синхронизируем с сервером
            try {
                await api.updateCartItem(variantId, newQuantity);
                // Перезагружаем корзину с сервера, чтобы получить обновлённые скидки
                await dataManager.loadCart();
                // Перерисовываем UI после загрузки обновлённых данных
                navigation.render();
            } catch (error) {
                console.error('Ошибка синхронизации корзины с сервером:', error);
            dataManager.saveCart();
            navigation.render();
            }
        } else {
            utils.showToast('Недостаточно товара на складе', 'error');
        }
    },

    getTotal() {
        return state.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    },

    calculateCashback() {
        return state.cart.reduce((sum, item) => {
            // Поддержка разных форматов полей
            const productId = item.productId || item.product_id || item.id;
            const quantity = item.cart_quantity || item.quantity || 1;
            
            const product = state.products.find(p => p.id === productId);
            if (!product) {
                utils.log('Product not found for cashback calculation:', productId);
                return sum;
            }
            
            // Используем cashback_rate из категории (из базы)
            const category = state.categories.find(c => c.id === product.category_id);
            const cashbackRate = category?.cashback_rate || 3.0;
            
            const price = item.price || 0;
            const itemTotal = price * quantity;
            const cashback = Math.round((itemTotal * cashbackRate) / 100);
            
            utils.log('Cashback for item:', { 
                productId, 
                quantity, 
                price,
                itemTotal, 
                cashbackRate, 
                cashback 
            });
            
            return sum + (isNaN(cashback) ? 0 : cashback);
        }, 0);
    },

    clear() {
        state.cart = [];
        dataManager.saveCart();
    }
};

// ======================
// FAVORITES MANAGEMENT
// ======================
const favorites = {
    async toggle(variantId, productId) {
        try {
            const result = await api.toggleFavorite(state.telegramUserId, variantId);
            
            // API возвращает {success: true, added: true/false}
            if (result.added) {
                state.favorites.push(variantId);
                utils.showToast('Добавлено в избранное');
            } else {
                state.favorites = state.favorites.filter(id => id !== variantId);
                utils.showToast('Удалено из избранного');
            }
            
            // Обновляем страницу если мы на избранном
            if (state.currentPage === 'favorites') {
                navigation.render();
            }
            
            return result;
        } catch (error) {
            utils.log('Favorite toggle error', error);
            utils.showToast('Ошибка: требуется авторизация', 'error');
            return null;
        }
    },

    isFavorite(variantId) {
        return state.favorites.includes(variantId);
    }
};

// ======================
// QUICK ADD MODAL (Быстрое добавление в корзину)
// ======================
const quickAddModal = {
    getVariantLabel(categoryName) {
        if (!categoryName) return 'вкус/цвет';
        
        const lowerCategory = categoryName.toLowerCase();
        
        // Логирование для отладки
        console.log('Category name:', categoryName, 'Lower:', lowerCategory);
        
        // Поды - только "цвет" (проверяем разные варианты названия)
        if (lowerCategory.includes('pod') || 
            lowerCategory.includes('под') || 
            lowerCategory.includes('одноразов')) {
            console.log('Matched: Поды -> цвет');
            return 'цвет';
        }
        // Испарители - "спецификация"
        if (lowerCategory.includes('испарител') || 
            lowerCategory.includes('картридж') ||
            lowerCategory.includes('coil')) {
            console.log('Matched: Испарители -> спецификацию');
            return 'спецификацию';
        }
        // Остальные категории - "вкус"
        console.log('Default: вкус');
        return 'вкус';
    },
    
    show(productId) {
        const product = state.products.find(p => p.id === productId);
        if (!product || !product.variants) return;
        
        const modal = document.getElementById('flavorModal');
        if (!modal) return;
        
        const modalContent = modal.querySelector('.modal-content');
        if (!modalContent) return;
        
        const variants = product.variants.filter(v => v.quantity > 0);
        
        // Получаем название категории по category_id
        const category = state.categories.find(c => c.id === product.category_id);
        const variantLabel = this.getVariantLabel(category?.name);
        
        modalContent.innerHTML = `
            <div class="modal-header">
                <h2>Выберите ${variantLabel}</h2>
                <button class="modal-close" onclick="quickAddModal.hide()">
                    <i class="ph ph-x"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="quick-add-product-info">
                    <div class="quick-add-brand">${product.brand || 'HOTSPOT'}</div>
                    <div class="quick-add-name">${product.name}</div>
                </div>
                <div class="flavors-grid">
                    ${variants.map(v => {
                        // Цена берется из товара, а не из варианта
                        const price = product.price || product.base_price || 0;
                        const oldPrice = product.old_price || null;
                        const discountPercent = product.discount_percent || 0;
                        
                        return `
                        <div class="flavor-option" 
                             data-variant-id="${v.id}"
                             onclick="quickAddModal.selectAndAdd(${v.id}, ${product.id})">
                            <div class="flavor-name">${v.flavor}</div>
                            <div class="flavor-stock ${v.quantity < 5 ? 'low' : ''}">
                                ${v.quantity} шт
                            </div>
                        </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
        
        modal.classList.remove('hidden');
    },

    hide() {
        const modal = document.getElementById('flavorModal');
        if (modal) modal.classList.add('hidden');
    },

    selectAndAdd(variantId, productId) {
        const product = state.products.find(p => p.id === productId);
        const variant = product?.variants?.find(v => v.id === variantId);
        
        if (product && variant) {
            cart.add(variant, product);
            this.hide();
        }
    }
};

// ======================
// PRODUCT MODAL
// ======================
const productModal = {
    show(product) {
        this.currentImageIndex = 0; // Сбрасываем индекс слайдера
        state.selectedProduct = product;
        state.selectedVariant = product.variants?.[0] || null;
        
        const modal = document.getElementById('productDetailModal');
        if (!modal) return;
        
        const modalContent = modal.querySelector('.modal-content');
        if (!modalContent) return;
        
        const variants = product.variants || [];
        const hasVariants = variants.length > 0;
        const firstVariant = variants[0] || { price: 0, quantity: 0, flavor: 'Недоступно' };
        
        // Цена берется из товара, а не из варианта
        const price = product.price || product.base_price || 0;
        const oldPrice = product.old_price || null;
        const discountPercent = product.discount_percent || 0;
        
        // Получаем название категории по category_id
        const category = state.categories.find(c => c.id === product.category_id);
        const variantLabel = quickAddModal.getVariantLabel(category?.name);
        
        const variantsHtml = variants.length > 0 ? `
            <div class="flavors-section">
                <div class="flavors-title">
                    <i class="ph ph-drop"></i>
                    Выберите ${variantLabel}:
                </div>
                <div class="flavors-grid">
                    ${variants.map((v, index) => `
                        <div class="flavor-option ${index === 0 ? 'selected' : ''} ${v.quantity === 0 ? 'disabled' : ''}"
                             data-variant-id="${v.id}"
                             data-variant-index="${index}">
                            <div class="flavor-name">${v.flavor}</div>
                            <div class="flavor-stock ${v.quantity < 5 ? 'low' : ''}">
                                ${v.quantity > 0 ? `${v.quantity} шт` : 'Нет в наличии'}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : '<p class="empty-state">Нет доступных вариантов</p>';
        
        // Создаём слайдер изображений для модального окна
        const images = product.images && product.images.length > 0 ? product.images : 
                      (product.image_url ? [{image_url: product.image_url}] : []);
        
        const modalImageSliderHtml = images.length > 0 ? `
            <div class="modal-image-slider" data-count="${images.length}">
                <div class="modal-slider-track">
                    ${images.map(img => `
                        <img src="${img.image_url}" alt="${product.name}">
                    `).join('')}
                </div>
                ${images.length > 1 ? `
                    <button class="slider-arrow prev" onclick="productModal.prevImage()">
                        <i class="ph ph-caret-left"></i>
                    </button>
                    <button class="slider-arrow next" onclick="productModal.nextImage()">
                        <i class="ph ph-caret-right"></i>
                    </button>
                ` : ''}
            </div>
            ${images.length > 1 ? `
                <div class="modal-slider-dots">
                    ${images.map((_, idx) => `
                        <div class="modal-slider-dot ${idx === 0 ? 'active' : ''}" onclick="productModal.goToImage(${idx})"></div>
                    `).join('')}
                </div>
            ` : ''}
        ` : `
            <div class="product-detail-image">
                <i class="ph ph-image"></i>
            </div>
        `;
        
        modalContent.innerHTML = `
            <div class="modal-header">
                <h2>${product.brand || product.name}</h2>
                <button class="modal-close" onclick="productModal.hide()">
                    <i class="ph ph-x"></i>
                </button>
            </div>
            <div class="modal-body">
                ${modalImageSliderHtml}
                
                <div class="product-detail-body">
                    <div class="product-detail-header">
                        <div class="product-detail-brand">${product.brand || 'HOTSPOT'}</div>
                        <div class="product-detail-name">${product.name}</div>
                        <div class="product-detail-price" id="modalPrice">
                            ${oldPrice ? `<span style="text-decoration: line-through; color: #999; font-size: 0.85em; margin-right: 8px;">${utils.formatPrice(oldPrice)}</span>` : ''}
                            ${utils.formatPrice(price)}
                        </div>
                    </div>
                    
                    ${(product.strength || product.volume || product.puffs || product.nicotine || product.battery || product.capacity || product.resistance) ? `
                        <div class="product-characteristics">
                            <div class="characteristics-grid">
                                ${product.strength ? `
                                    <div class="characteristic-item">
                                        <i class="ph ph-fire"></i>
                                        <div>
                                            <div class="char-label">Крепость</div>
                                            <div class="char-value">${product.strength}</div>
                                        </div>
                                    </div>
                                ` : ''}
                                ${product.volume ? `
                                    <div class="characteristic-item">
                                        <i class="ph ph-flask"></i>
                                        <div>
                                            <div class="char-label">Объём</div>
                                            <div class="char-value">${product.volume}</div>
                                        </div>
                                    </div>
                                ` : ''}
                                ${product.puffs ? `
                                    <div class="characteristic-item">
                                        <i class="ph ph-cloud"></i>
                                        <div>
                                            <div class="char-label">Затяжки</div>
                                            <div class="char-value">${product.puffs}</div>
                                        </div>
                                    </div>
                                ` : ''}
                                ${product.nicotine ? `
                                    <div class="characteristic-item">
                                        <i class="ph ph-drop"></i>
                                        <div>
                                            <div class="char-label">Никотин</div>
                                            <div class="char-value">${product.nicotine}</div>
                                        </div>
                                    </div>
                                ` : ''}
                                ${product.battery ? `
                                    <div class="characteristic-item">
                                        <i class="ph ph-battery-charging"></i>
                                        <div>
                                            <div class="char-label">Батарея</div>
                                            <div class="char-value">${product.battery}</div>
                                        </div>
                                    </div>
                                ` : ''}
                                ${product.capacity ? `
                                    <div class="characteristic-item">
                                        <i class="ph ph-flask"></i>
                                        <div>
                                            <div class="char-label">Ёмкость</div>
                                            <div class="char-value">${product.capacity}</div>
                                        </div>
                                    </div>
                                ` : ''}
                                ${product.resistance ? `
                                    <div class="characteristic-item">
                                        <i class="ph ph-lightning"></i>
                                        <div>
                                            <div class="char-label">Сопротивление</div>
                                            <div class="char-value">${product.resistance}</div>
                                        </div>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    ` : ''}
                    
                    ${product.description ? `
                        <div class="product-detail-description">
                            ${product.description}
                        </div>
                    ` : ''}
                    
                    ${variantsHtml}
                    
                    <div class="product-detail-actions">
                        <label class="favorite-checkbox-wrapper-modal" onclick="event.stopPropagation();">
                            <input type="checkbox" 
                                   class="favorite-checkbox-modal" 
                                   id="modalFavoriteCheckbox"
                                   data-variant-id="${firstVariant.id}" 
                                   data-product-id="${product.id}"
                                   ${favorites.isFavorite(firstVariant.id) ? 'checked' : ''}>
                        </label>
                        ${hasVariants && firstVariant.quantity > 0 ? `
                            <button class="btn-add-to-cart-modal" 
                                    id="modalAddToCartBtn"
                                    onclick="event.stopPropagation();">
                                <i class="ph ph-shopping-cart"></i>
                                <span>В корзину</span>
                            </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
        
        modal.classList.remove('hidden');
        this.attachEventListeners();
    },

    hide() {
        const modal = document.getElementById('productDetailModal');
        if (modal) modal.classList.add('hidden');
        state.selectedProduct = null;
        state.selectedVariant = null;
    },

    attachEventListeners() {
        // Выбор вкуса
        document.querySelectorAll('.flavor-option').forEach(option => {
            option.addEventListener('click', () => {
                if (option.classList.contains('disabled')) return;
                
                // Убираем выделение со всех
                document.querySelectorAll('.flavor-option').forEach(o => o.classList.remove('selected'));
                
                // Выделяем текущий
                option.classList.add('selected');
                
                // Обновляем выбранный вариант
                const variantId = parseInt(option.dataset.variantId);
                const variantIndex = parseInt(option.dataset.variantIndex);
                
                if (state.selectedProduct && state.selectedProduct.variants) {
                    state.selectedVariant = state.selectedProduct.variants[variantIndex];
                    
                    // Обновляем цену
                    const priceEl = document.getElementById('modalPrice');
                    if (priceEl) {
                        const variant = state.selectedVariant;
                        const product = state.selectedProduct;
                        
                        // Цена берется из товара, а не из варианта
                        const price = product.price || product.base_price || 0;
                        const oldPrice = product.old_price || null;
                        const discountPercent = product.discount_percent || 0;
                        
                        priceEl.innerHTML = `
                            ${oldPrice ? `<span style="text-decoration: line-through; color: #999; font-size: 0.85em; margin-right: 8px;">${utils.formatPrice(oldPrice)}</span>` : ''}
                            ${utils.formatPrice(price)}
                        `;
                    }
                    
                    // Обновляем кнопку добавления
                    const addBtn = document.getElementById('modalAddToCartBtn');
                    if (addBtn) {
                        if (state.selectedVariant.quantity > 0) {
                            addBtn.style.display = 'flex';
                            addBtn.innerHTML = '<i class="ph ph-shopping-cart"></i><span>В корзину</span>';
                        } else {
                            addBtn.style.display = 'none';
                        }
                    }
                    
                    // Обновляем чекбокс избранного
                    const favCheckbox = document.getElementById('modalFavoriteCheckbox');
                    if (favCheckbox) {
                        favCheckbox.dataset.variantId = variantId;
                        favCheckbox.checked = favorites.isFavorite(variantId);
                    }
                }
            });
        });
        
        // Добавить в корзину
        const addBtn = document.getElementById('modalAddToCartBtn');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                if (state.selectedProduct && state.selectedVariant) {
                    cart.add(state.selectedVariant, state.selectedProduct);
                    this.hide();
                }
            });
        }
        
        // Избранное (чекбокс)
        const favCheckbox = document.getElementById('modalFavoriteCheckbox');
        if (favCheckbox) {
            favCheckbox.addEventListener('change', async () => {
                const variantId = parseInt(favCheckbox.dataset.variantId);
                const productId = parseInt(favCheckbox.dataset.productId);
                await favorites.toggle(variantId, productId);
                
                // Обновляем состояние чекбокса
                favCheckbox.checked = favorites.isFavorite(variantId);
            });
        }
    },
    
    currentImageIndex: 0,
    
    goToImage(index) {
        const slider = document.querySelector('.modal-image-slider');
        if (!slider) return;
        
        const track = slider.querySelector('.modal-slider-track');
        const dots = document.querySelectorAll('.modal-slider-dot');
        
        if (track && dots.length > 0) {
            this.currentImageIndex = index;
            track.style.transform = `translateX(-${index * 100}%)`;
            
            dots.forEach((dot, idx) => {
                dot.classList.toggle('active', idx === index);
            });
        }
    },
    
    nextImage() {
        const slider = document.querySelector('.modal-image-slider');
        if (!slider) return;
        
        const imageCount = parseInt(slider.dataset.count) || 1;
        const nextIndex = (this.currentImageIndex + 1) % imageCount;
        this.goToImage(nextIndex);
    },
    
    prevImage() {
        const slider = document.querySelector('.modal-image-slider');
        if (!slider) return;
        
        const imageCount = parseInt(slider.dataset.count) || 1;
        const prevIndex = (this.currentImageIndex - 1 + imageCount) % imageCount;
        this.goToImage(prevIndex);
    }
};

// ======================
// ORDER DETAIL MODAL
// ======================
const orderDetailModal = {
    show(orderId) {
        const order = state.orders.find(o => o.id === orderId);
        if (!order) {
            utils.showToast('Заказ не найден', 'error');
            return;
        }
        
        const modal = document.getElementById('orderDetailModal');
        if (!modal) return;
        
        const modalContent = modal.querySelector('.modal-content');
        if (!modalContent) return;
        
        const statusColors = {
            'pending': 'orange',
            'confirmed': 'blue',
            'completed': 'green',
            'cancelled': 'red'
        };
        
        const statusNames = {
            'pending': 'В обработке',
            'confirmed': 'Подтверждён',
            'completed': 'Выполнен',
            'cancelled': 'Отменён'
        };
        
        // Парсим items если это строка
        let items = [];
        try {
            items = typeof order.items === 'string' ? JSON.parse(order.items) : order.items;
        } catch (e) {
            items = [];
        }
        
        const itemsHtml = items.map(item => `
            <div class="order-detail-item">
                <div class="order-item-info">
                    <div class="order-item-name">${item.name || 'Товар'}</div>
                    <div class="order-item-flavor">${item.flavor || ''}</div>
                </div>
                <div class="order-item-qty">x${item.quantity}</div>
                <div class="order-item-price">${utils.formatPrice(item.price * item.quantity)}</div>
            </div>
        `).join('');
        
        modalContent.innerHTML = `
            <div class="modal-header">
                <h2>Заказ #${order.id}</h2>
                <button class="modal-close" onclick="orderDetailModal.hide()">
                    <i class="ph ph-x"></i>
                </button>
            </div>
            <div class="modal-body">
                <div class="order-detail-status">
                    <span class="order-status status-${statusColors[order.status] || 'grey'}">
                        ${statusNames[order.status] || order.status}
                    </span>
                    <span class="order-detail-date">${new Date(order.created_at).toLocaleString('ru-RU')}</span>
                </div>
                
                <div class="order-detail-section">
                    <h3>Товары</h3>
                    <div class="order-detail-items">
                        ${itemsHtml || '<p>Нет товаров</p>'}
                    </div>
                </div>
                
                <div class="order-detail-section">
                    <h3>Информация о доставке</h3>
                    <div class="order-detail-info">
                        ${order.delivery_type === 'pickup' ? `
                            <div class="info-row">
                                <span class="info-label">Тип:</span>
                                <span class="info-value">Самовывоз</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Пункт выдачи:</span>
                                <span class="info-value">${order.pickup_location || 'Не указан'}</span>
                            </div>
                        ` : `
                            <div class="info-row">
                                <span class="info-label">Тип:</span>
                                <span class="info-value">Доставка</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label">Адрес:</span>
                                <span class="info-value">${order.delivery_address || 'Не указан'}</span>
                            </div>
                        `}
                    </div>
                </div>
                
                <div class="order-detail-section">
                    <h3>Контактные данные</h3>
                    <div class="order-detail-info">
                        <div class="info-row">
                            <span class="info-label">Имя:</span>
                            <span class="info-value">${order.customer_name || 'Не указано'}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Телефон:</span>
                            <span class="info-value">${order.customer_phone || 'Не указан'}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Способ оплаты:</span>
                            <span class="info-value">${
                                order.payment_method === 'sbp_online' ? 'СБП (онлайн)' :
                                order.payment_method === 'sbp_pickup' ? 'СБП (при получении)' :
                                order.payment_method === 'cash' ? 'Наличные' :
                                order.payment_method === 'balance' ? 'Баланс' : 'Не указан'
                            }</span>
                        </div>
                    </div>
                </div>
                
                <div class="order-detail-section">
                    <h3>Итого</h3>
                    <div class="order-detail-summary">
                        <div class="summary-row">
                            <span>Товары:</span>
                            <span>${utils.formatPrice(order.subtotal || 0)}</span>
                        </div>
                        ${order.delivery_cost ? `
                            <div class="summary-row">
                                <span>Доставка:</span>
                                <span>${utils.formatPrice(order.delivery_cost)}</span>
                            </div>
                        ` : ''}
                        ${order.discount ? `
                            <div class="summary-row">
                                <span>Скидка:</span>
                                <span>-${utils.formatPrice(order.discount)}</span>
                            </div>
                        ` : ''}
                        ${order.balance_used && order.balance_used > 0 ? `
                            <div class="summary-row" style="color: #ff6b35;">
                                <span>Оплачено балансом:</span>
                                <span>-${utils.formatPrice(order.balance_used)}</span>
                            </div>
                        ` : ''}
                        <div class="summary-row total">
                            <span>Итого к оплате:</span>
                            <span>${utils.formatPrice(order.total || 0)}</span>
                        </div>
                        ${order.cashback_earned && order.cashback_earned > 0 ? `
                            <div class="cashback-info">
                                💰 Начислено кешбэка: ${utils.formatPrice(order.cashback_earned)}
                            </div>
                        ` : ''}
                    </div>
                </div>
                
                ${order.status === 'pending' ? `
                    <button class="btn btn-primary btn-full btn-contact-manager-big" onclick="orderDetailModal.contactManager(${order.id})">
                        <i class="ph ph-telegram-logo"></i>
                        Связаться с менеджером
                    </button>
                ` : ''}
            </div>
        `;
        
        modal.classList.remove('hidden');
    },
    
    hide() {
        const modal = document.getElementById('orderDetailModal');
        if (modal) modal.classList.add('hidden');
    },
    
    contactManager(orderId) {
        const order = state.orders.find(o => o.id === orderId);
        if (!order) return;
        
        // Формируем сообщение
        let items = [];
        try {
            items = typeof order.items === 'string' ? JSON.parse(order.items) : order.items;
        } catch (e) {
            items = [];
        }
        
        const itemsList = items.map(item => 
            `• ${item.name}${item.flavor ? ' (' + item.flavor + ')' : ''} x${item.quantity} - ${utils.formatPrice(item.price * item.quantity)}`
        ).join('\n');
        
        const fullTotal = order.total_amount || order.subtotal + order.delivery_cost - order.discount || order.total || 0;
        const message = `Здравствуйте! У меня вопрос по заказу #${order.id}\n\n` +
            `Статус: ${order.status}\n` +
            `Дата: ${new Date(order.created_at).toLocaleString('ru-RU')}\n` +
            `Сумма: ${utils.formatPrice(fullTotal)}\n\n` +
            `Товары:\n${itemsList}`;
        
        const encodedMessage = encodeURIComponent(message);
        window.open(`https://t.me/${CONFIG.MANAGER_TELEGRAM.replace('@', '')}?text=${encodedMessage}`, '_blank');
        
        this.hide();
    }
};

// ======================
// COMPONENTS
// ======================
const components = {
    categoryCard(category) {
        // Поддержка изображений для категорий
        const imageHtml = category.image_url 
            ? `<img src="${category.image_url}" alt="${category.name}" class="category-image">`
            : `<i class="ph ph-package"></i>`;
        
        return `
            <button class="category-card" data-category-id="${category.id}">
                ${imageHtml}
                <span class="category-name">${category.name}</span>
            </button>
        `;
    },

    productCard(product) {
        const variant = product.variants?.[0];
        if (!variant) return '';

        // Подсчёт общего количества всех вариантов
        const totalQuantity = product.variants?.reduce((sum, v) => sum + (v.quantity || 0), 0) || 0;

        const isFav = favorites.isFavorite(variant.id);
        const inStock = totalQuantity > 0;
        const lowStock = totalQuantity > 0 && totalQuantity < 5;
        const hasMultipleVariants = product.variants && product.variants.length > 1;
        
        // Берём кешбэк из категории
        const category = state.categories.find(c => c.id === product.category_id);
        const cashbackRate = category?.cashback_rate || 3.0;
        
        // Цена берется из товара, а не из варианта
        const price = product.price || variant.price || product.base_price || 0;
        const oldPrice = product.old_price || null;
        const discountPercent = product.discount_percent || 0;
        
        // Логируем для отладки (первый товар)
        if (!window._priceLogged) {
            utils.log('Product pricing:', {
                productId: product.id,
                productName: product.name,
                'product.price': product.price,
                'variant.price': variant.price,
                'product.base_price': product.base_price,
                'finalPrice': price
            });
            window._priceLogged = true;
        }
        
        const cashbackAmount = Math.round((price * cashbackRate) / 100);
        
        // Проверяем наличие скидки на товаре
        const hasDiscount = oldPrice && oldPrice > price;

        // Создаём слайдер изображений
        const images = product.images && product.images.length > 0 ? product.images : 
                      (product.image_url ? [{image_url: product.image_url}] : []);
        
        const imageSliderHtml = images.length > 0 ? `
                    <div class="product-image">
                <div class="product-image-slider" data-count="${images.length}" data-product-id="${product.id}">
                    ${images.map((img, idx) => `
                        <img src="${img.image_url}" alt="${product.name}" class="${idx === 0 ? 'active' : ''}" data-index="${idx}">
                    `).join('')}
                    ${images.length > 1 ? `
                        <div class="slider-dots">
                            ${images.map((_, idx) => `
                                <div class="slider-dot ${idx === 0 ? 'active' : ''}" data-index="${idx}"></div>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
                        ${inStock ? `<div class="cashback-badge" title="Вернётся ${cashbackAmount}₽ на баланс">+${cashbackAmount}₽</div>` : ''}
                    </div>
                ` : `
                    <div class="product-image">
                        <i class="ph ph-image"></i>
                        ${inStock ? `<div class="cashback-badge" title="Вернётся ${cashbackAmount}₽ на баланс">+${cashbackAmount}₽</div>` : ''}
                    </div>
        `;
        
        return `
            <div class="product-card ${!inStock ? 'out-of-stock' : ''} ${hasDiscount ? 'has-discount' : ''}" data-product-id="${product.id}">
                ${imageSliderHtml}
                <div class="product-info">
                    <div class="product-brand">${product.brand || 'HOTSPOT'}</div>
                    <div class="product-name">${product.name}</div>
                    ${(product.strength || product.volume) ? `
                        <div class="product-specs">
                            ${product.strength ? `
                                <div class="spec-item">
                                    <i class="ph ph-fire"></i>
                                    <span>${product.strength}</span>
                                </div>
                            ` : ''}
                            ${product.volume ? `
                                <div class="spec-item">
                                    <i class="ph ph-flask"></i>
                                    <span>${product.volume}</span>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                    <div class="product-footer">
                        <div>
                            <div class="product-price">
                                ${hasDiscount ? `<span style="text-decoration: line-through; color: #999; font-size: 0.85em; margin-right: 6px;">${utils.formatPrice(oldPrice)}</span>` : ''}
                                <span>${utils.formatPrice(price)}</span>
                            </div>
                            ${inStock ? `
                                <div class="product-stock ${lowStock ? 'low-stock' : ''}">
                                    <i class="ph ph-package"></i>
                                    ${totalQuantity} шт
                                </div>
                            ` : `
                                <div class="product-stock low-stock">
                                    <i class="ph ph-x-circle"></i>
                                    Нет в наличии
                                </div>
                            `}
                        </div>
                        <div class="product-card-actions">
                            <label class="favorite-checkbox-wrapper" onclick="event.stopPropagation();">
                                <input type="checkbox" 
                                       class="favorite-checkbox" 
                                       data-variant-id="${variant.id}" 
                                       data-product-id="${product.id}"
                                       ${isFav ? 'checked' : ''}>
                            </label>
                            ${inStock ? `
                                <button class="btn-icon-small btn-quick-add" 
                                        data-product-id="${product.id}"
                                        onclick="event.stopPropagation(); quickAddModal.show(${product.id});"
                                        title="Быстро добавить">
                                    <i class="ph ph-shopping-cart-simple"></i>
                                </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    cartItem(item) {
        return `
            <div class="cart-item" data-variant-id="${item.variantId}">
                <div class="cart-item-image">
                    ${item.image ? `<img src="${item.image}" alt="${item.name}">` : '<i class="ph ph-image"></i>'}
                </div>
                <div class="cart-item-info">
                    <h3>${item.brand || item.name}</h3>
                    <p>${item.flavor}</p>
                    <span class="cart-item-price">${utils.formatPrice(item.price)}</span>
                </div>
                <div class="cart-item-controls">
                    <button class="btn-icon quantity-btn" data-action="decrease" data-variant-id="${item.variantId}">
                        <i class="ph ph-minus"></i>
                    </button>
                    <span class="quantity">${item.quantity}</span>
                    <button class="btn-icon quantity-btn" data-action="increase" data-variant-id="${item.variantId}">
                        <i class="ph ph-plus"></i>
                    </button>
                    <button class="btn-icon remove-btn" data-variant-id="${item.variantId}">
                        <i class="ph ph-trash"></i>
                    </button>
                </div>
            </div>
        `;
    },

    orderCard(order) {
        const statusColors = {
            'pending': 'orange',
            'confirmed': 'blue',
            'completed': 'green',
            'cancelled': 'red'
        };

        const statusNames = {
            'pending': 'В обработке',
            'confirmed': 'Подтверждён',
            'completed': 'Выполнен',
            'cancelled': 'Отменён'
        };

        // Показываем итоговую сумму к оплате (с учетом всех скидок и баланса)
        const fullTotal = order.total || 0;

        return `
            <div class="order-card" data-order-id="${order.id}" onclick="orderDetailModal.show(${order.id})">
                <div class="order-header">
                    <span class="order-number">Заказ #${order.id}</span>
                    <span class="order-status status-${statusColors[order.status] || 'grey'}">
                        ${statusNames[order.status] || order.status}
                    </span>
                </div>
                <div class="order-info">
                    <p class="order-date">${new Date(order.created_at).toLocaleString('ru-RU')}</p>
                    <p class="order-total">${utils.formatPrice(fullTotal)}</p>
                </div>
                <i class="ph ph-caret-right order-arrow"></i>
            </div>
        `;
    }
};

// ======================
// PAGES
// ======================
const pages = {
    home() {
        const categoriesHtml = state.categories
            .map(c => components.categoryCard(c))
            .join('');

        const hotProducts = state.products
            .filter(p => p.variants?.some(v => v.quantity > 0))
            .slice(0, 12);

        const productsHtml = hotProducts
            .map(p => components.productCard(p))
            .join('');

        return `
            <div class="page-content">
                <div class="info-banner">
                    <i class="ph ph-fire"></i>
                    <span>🔥 Горячие новинки каждую неделю!</span>
                </div>
                
                <div class="section">
                    <div class="section-header">
                        <h2>Категории</h2>
                    </div>
                    <div class="categories-grid">
                        ${categoriesHtml || '<p>Категории не найдены</p>'}
                    </div>
                </div>

                <div class="section">
                    <div class="section-header">
                        <h2>🔥 Популярные товары</h2>
                    </div>
                    <div class="products-grid">
                        ${productsHtml || '<p>Товары не найдены</p>'}
                    </div>
                </div>
            </div>
        `;
    },

    category(categoryId) {
        const category = state.categories.find(c => c.id === parseInt(categoryId));
        if (!category) return '<p>Категория не найдена</p>';

        const products = state.products.filter(p => p.category_id === category.id);
        
        if (products.length === 0) {
            return `
                <div class="page-content">
                    <div class="section">
                        <div class="section-header">
                            <h2>${category.name}</h2>
                        </div>
                        <p>Товары не найдены</p>
                    </div>
                </div>
            `;
        }
        
        // Группировка по брендам
        const brandGroups = {};
        products.forEach(p => {
            const brand = p.brand || 'Без бренда';
            if (!brandGroups[brand]) {
                brandGroups[brand] = [];
            }
            brandGroups[brand].push(p);
        });
        
        // Сортировка брендов по алфавиту
        const sortedBrands = Object.keys(brandGroups).sort();
        
        // Генерация HTML для каждого бренда
        const brandsHtml = sortedBrands.map((brand, brandIndex) => {
            const brandProducts = brandGroups[brand];
            const showMoreNeeded = brandProducts.length > 2;
            
            // Показываем первые 2 товара, остальные скрываем
            const visibleProducts = brandProducts.slice(0, 2);
            const hiddenProducts = showMoreNeeded ? brandProducts.slice(2) : [];
            
            const visibleHtml = visibleProducts.map(p => components.productCard(p)).join('');
            const hiddenHtml = hiddenProducts.map(p => components.productCard(p)).join('');
            
            return `
                <div class="brand-group">
                    <div class="brand-header">
                        <h3 class="brand-name">${brand}</h3>
                        <span class="brand-count">${brandProducts.length} товар(ов)</span>
                    </div>
                    <div class="products-grid brand-products-visible-${brandIndex}">
                        ${visibleHtml}
                    </div>
                    ${showMoreNeeded ? `
                        <div class="products-grid brand-products-hidden-${brandIndex}" style="display: none;">
                            ${hiddenHtml}
                        </div>
                        <button class="btn-show-more" data-brand-index="${brandIndex}">
                            <i class="ph ph-caret-down"></i>
                            Показать ещё ${hiddenProducts.length}
                        </button>
                    ` : ''}
                </div>
            `;
        }).join('');

        return `
            <div class="page-content">
                <div class="section">
                    <div class="section-header">
                        <h2>${category.name}</h2>
                        <span class="category-total">${products.length} товар(ов)</span>
                    </div>
                    ${brandsHtml}
                </div>
            </div>
        `;
    },

    search() {
        return `
            <div class="page-content search-page">
                <div class="search-input-wrapper">
                    <input type="text" 
                           id="searchInput" 
                           class="search-input" 
                           placeholder="Поиск товаров...">
                </div>
                <div id="searchResults" class="search-results-container"></div>
            </div>
        `;
    },

    favorites() {
        const favoriteProducts = state.products.filter(p => 
            p.variants?.some(v => favorites.isFavorite(v.id))
        );

        if (favoriteProducts.length === 0) {
            return `
                <div class="page-content">
                    <div class="empty-state">
                        <i class="ph ph-heart"></i>
                        <h3>Избранное пусто</h3>
                        <p>Добавляйте понравившиеся товары в избранное</p>
                    </div>
                </div>
            `;
        }

        const productsHtml = favoriteProducts
            .map(p => components.productCard(p))
            .join('');

        return `
            <div class="page-content">
                <div class="section">
                    <div class="section-header">
                        <h2>Избранное</h2>
                    </div>
                    <div class="products-grid">
                        ${productsHtml}
                    </div>
                </div>
            </div>
        `;
    },

    cart() {
        if (state.cart.length === 0) {
            return `
                <div class="page-content">
                    <div class="empty-state">
                        <i class="ph ph-shopping-cart"></i>
                        <h3>Корзина пуста</h3>
                        <p>Добавьте товары для оформления заказа</p>
                    </div>
                </div>
            `;
        }

        const itemsHtml = state.cart.map(item => components.cartItem(item)).join('');
        const subtotal = cart.getTotal();
        const cashbackAmount = cart.calculateCashback();
        const userBalance = state.user?.balance || 0;
        
        // Автоматические скидки
        const autoDiscount = state.autoDiscounts?.total_discount || 0;
        const finalTotal = subtotal - autoDiscount;

        return `
            <div class="page-content">
                <div class="section">
                    <div class="cart-items">
                        ${itemsHtml}
                    </div>
                    
                    <div class="cart-summary">
                        <div class="summary-row">
                            <span>Товары:</span>
                            <span id="cartSubtotal">${utils.formatPrice(subtotal)}</span>
                        </div>
                        ${autoDiscount > 0 ? `
                        <div class="summary-row discount-row">
                            <span><i class="ph ph-tag"></i> Скидка:</span>
                            <span class="discount-amount">-${utils.formatPrice(autoDiscount)}</span>
                        </div>
                        ${state.autoDiscounts?.applied_discounts?.length > 0 ? `
                        <div class="applied-discounts-info">
                            ${state.autoDiscounts.applied_discounts.map(d => `
                                <div class="discount-tag">🎁 ${d.name}</div>
                            `).join('')}
                        </div>
                        ` : ''}
                        ` : ''}
                        ${cashbackAmount > 0 ? `
                        <div class="summary-row cashback-row">
                            <span><i class="ph ph-coin"></i> Кешбэк вернётся:</span>
                            <span class="cashback-amount">+${utils.formatPrice(cashbackAmount)}</span>
                        </div>
                        ` : ''}
                        
                        <!-- Строка для использованного баланса (скрыта по умолчанию) -->
                        ${userBalance > 0 ? `
                        <div class="summary-row" id="balanceUsedRow" style="display: none; color: #ff6b00;">
                            <span><i class="ph ph-wallet"></i> Оплачено балансом:</span>
                            <span id="balanceUsedAmount">-${utils.formatPrice(0)}</span>
                        </div>
                        ` : ''}
                        
                        <div class="summary-row total">
                            <span>Итого:</span>
                            <span id="cartTotal">${utils.formatPrice(finalTotal)}</span>
                        </div>
                        
                        <!-- Кнопка использования баланса -->
                        ${userBalance > 0 ? `
                        <div class="balance-section">
                            <button class="balance-toggle-compact" id="toggleBalanceBtn" data-active="false">
                                <i class="ph ph-wallet"></i>
                                <span>Баланс: ${utils.formatPrice(userBalance)}</span>
                                <div class="balance-check">
                                    <i class="ph ph-check"></i>
                                </div>
                            </button>
                        </div>
                        ` : ''}
                        
                        <p class="cart-note">* Стоимость доставки будет рассчитана при оформлении заказа</p>
                        <button class="btn btn-primary btn-full" id="checkoutBtn">
                            <i class="ph ph-shopping-bag"></i>
                            Оформить заказ
                        </button>
                    </div>
                </div>
            </div>
        `;
    },

    profile() {
        const ordersHtml = state.orders
            .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
            .slice(0, 10)
            .map(o => components.orderCard(o))
            .join('');

        return `
            <div class="page-content">
                <!-- Личная информация -->
                <div class="profile-section">
                    <div class="profile-section-title">
                        <i class="ph ph-user-circle"></i>
                        Личная информация
                    </div>
                    <div class="profile-info-row">
                        <span class="profile-info-label">Имя:</span>
                        <span class="profile-info-value">${state.user?.first_name || 'Не указано'}</span>
                    </div>
                    <div class="profile-info-row">
                        <span class="profile-info-label">Username:</span>
                        <span class="profile-info-value">${state.user?.username ? '@' + state.user.username : 'Не указан'}</span>
                    </div>
                    <div class="profile-info-row">
                        <span class="profile-info-label">Telegram ID:</span>
                        <span class="profile-info-value">${state.telegramUserId}</span>
                    </div>
                    <div class="profile-info-row">
                        <span class="profile-info-label">Телефон:</span>
                        <span class="profile-info-value">${state.user?.phone || 'Не указан'}</span>
                    </div>
                    <div class="profile-info-row">
                        <span class="profile-info-label">Баланс:</span>
                        <span class="profile-info-value">${utils.formatPrice(state.user?.balance || 0)}</span>
                    </div>
                </div>

                <!-- Промокод -->
                <div class="profile-section">
                    <div class="profile-section-title">
                        <i class="ph ph-ticket"></i>
                        Промокод
                    </div>
                    <div class="promo-input-wrapper">
                        <input type="text" 
                               id="promocodeInput" 
                               class="promo-input" 
                               placeholder="Введите промокод">
                        <button class="btn-apply-promo" id="applyPromoBtn">
                            Применить
                        </button>
                    </div>
                </div>

                <!-- Связь с менеджером -->
                <div class="profile-section">
                    <div class="profile-section-title">
                        <i class="ph ph-chats-circle"></i>
                        Поддержка
                    </div>
                    <button class="btn-contact-manager" id="contactManagerBtn">
                        <i class="ph ph-telegram-logo"></i>
                        Написать менеджеру
                    </button>
                    <button class="btn-contact-developer" id="contactDeveloperBtn" style="margin-top: 10px;">
                        <i class="ph ph-code"></i>
                        Вопросы по разработке
                    </button>
                </div>

                <!-- История заказов -->
                <div class="section">
                    <div class="section-header">
                        <h2>Мои заказы</h2>
                    </div>
                    <div class="orders-list">
                        ${ordersHtml || '<p class="empty-state">У вас пока нет заказов</p>'}
                    </div>
                </div>
            </div>
        `;
    }
};

// ======================
// NAVIGATION
// ======================
const navigation = {
    goTo(page, params = {}) {
        utils.log('Navigation', { page, params });
        
        state.currentPage = page;
        Object.assign(state, params);
        
        this.updateNav();
        this.render();
        this.updateBackButton();
    },

    render() {
        // Если пользователь забанен - не рендерить страницы
        if (document.body.classList.contains('user-banned')) {
            return;
        }
        
        const app = document.getElementById('app');
        if (!app) return;

        let html = '';
        
        switch (state.currentPage) {
            case 'home':
                html = pages.home();
                break;
            case 'category':
                html = pages.category(state.currentCategoryId);
                break;
            case 'search':
                html = pages.search();
                break;
            case 'favorites':
                html = pages.favorites();
                break;
            case 'cart':
                html = pages.cart();
                break;
            case 'profile':
                html = pages.profile();
                break;
            default:
                html = pages.home();
        }

        app.innerHTML = html;
        this.attachEventListeners();
        
        // Автофокус на поиске
        if (state.currentPage === 'search') {
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.focus();
                searchInput.addEventListener('input', this.handleSearch.bind(this));
            }
        }
        
        // События профиля
        if (state.currentPage === 'profile') {
            const applyPromoBtn = document.getElementById('applyPromoBtn');
            if (applyPromoBtn) {
                applyPromoBtn.addEventListener('click', this.handlePromocode.bind(this));
            }
            
            const contactBtn = document.getElementById('contactManagerBtn');
            if (contactBtn) {
                contactBtn.addEventListener('click', () => {
                    window.open(`https://t.me/${CONFIG.MANAGER_TELEGRAM.replace('@', '')}`, '_blank');
                });
            }
            
            const contactDevBtn = document.getElementById('contactDeveloperBtn');
            if (contactDevBtn) {
                contactDevBtn.addEventListener('click', () => {
                    window.open('https://t.me/x32asm', '_blank');
                });
            }
        }
    },

    updateNav() {
        document.querySelectorAll('.nav-item').forEach(item => {
            const page = item.dataset.page;
            if (page === state.currentPage) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    },

    updateBackButton() {
        const backBtn = document.getElementById('backBtn');
        if (!backBtn) return;
        
        const showBack = state.currentPage === 'category';
        backBtn.style.display = showBack ? 'flex' : 'none';
    },

    handleSearch(e) {
        const query = e.target.value.trim();
        const resultsContainer = document.getElementById('searchResults');
        
        if (!query || query.length < 2) {
            resultsContainer.innerHTML = '';
            return;
        }

        const normalize = (text) => text.toLowerCase().replace(/[^\wа-яё]/gi, ' ').replace(/\s+/g, ' ').trim();
        
        // Специальные замены для улучшения поиска
        const specialCases = {
            'вака': 'waka',
            'вака смо': 'waka',
            'вска': 'waka',
            'хрос': 'xros',
            'иксрос': 'xros',
            'кросс': 'xros',
            'анима': 'annima',
            'аннима': 'annima',
            'вапоресо': 'vaporesso',
            'вапорессо': 'vaporesso',
            'кс': 'cs',
            'блад': 'blood',
            'блуд': 'blood'
        };
        
        let queryLower = normalize(query);
        
        // Проверяем специальные случаи
        if (specialCases[queryLower]) {
            queryLower = specialCases[queryLower];
        }
        
        const queryTranslit = utils.transliterate(queryLower);

        const resultsWithScore = state.products.map(p => {
            const name = normalize(p.name || '');
            const nameTrans = utils.transliterate(name);
            const brand = normalize(p.brand || '');
            
            let score = 0;
            
            // 1. ПРЯМОЕ СОВПАДЕНИЕ В НАЗВАНИИ
            if (name === queryLower) {
                score = 100000;
            }
            else if (name.startsWith(queryLower)) {
                score = 50000;
            }
            else if (name.includes(queryLower)) {
                score = 25000;
            }
            
            // 2. ТРАНСЛИТ ЗАПРОСА → ПОИСК В НАЗВАНИИ (для кириллицы)
            // "ана" → "ana" → ищем "ANNIMA"
            else if (name.startsWith(queryTranslit) && queryTranslit !== queryLower) {
                score = 40000;
            }
            else if (name.includes(queryTranslit) && queryTranslit !== queryLower) {
                score = 20000;
            }
            
            // 3. ТРАНСЛИТ НАЗВАНИЯ → ПОИСК ЗАПРОСА (для латиницы)
            // "ana" → ищем в транслите "Анархия" = "anarhiya"
            else if (nameTrans.startsWith(queryLower) && nameTrans !== name) {
                score = 35000;
            }
            else if (nameTrans.includes(queryLower) && nameTrans !== name) {
                score = 18000;
            }
            
            // 4. БРЕНД
            else if (brand === queryLower) {
                score = 15000;
            }
            else if (brand.startsWith(queryLower)) {
                score = 12000;
            }
            else if (brand.includes(queryLower)) {
                score = 10000;
            }
            
            // 5. ПОИСК ПО ВКУСАМ (полное совпадение слов)
            else if (p.variants && p.variants.length > 0) {
                const queryWords = queryLower.split(' ').filter(w => w.length >= 2);
                let flavorScore = 0;
                
                p.variants.forEach(v => {
                    const flavor = normalize(v.flavor || '');
                    const flavorWords = flavor.split(' ').filter(w => w.length >= 2);
                    
                    // Проверяем полное совпадение слов
                    queryWords.forEach(qw => {
                        flavorWords.forEach(fw => {
                            if (fw === qw) {
                                flavorScore += 3000; // Полное совпадение слова
                            }
                        });
                    });
                });
                
                if (flavorScore > 0) score = flavorScore;
            }
            
            // 6. ЧАСТИЧНОЕ СОВПАДЕНИЕ ПО СЛОВАМ В НАЗВАНИИ
            if (score === 0) {
                const queryWords = queryLower.split(' ').filter(w => w.length >= 2);
                const nameWords = name.split(' ').filter(w => w.length >= 2);
                
                if (queryWords.length > 0 && nameWords.length > 0) {
                    let matches = 0;
                    queryWords.forEach(qw => {
                        nameWords.forEach(nw => {
                            if (nw.startsWith(qw) && qw.length >= 3) matches += 2;
                            else if (nw.includes(qw) && qw.length >= 4) matches += 1;
                        });
                    });
                    if (matches > 0) score = 2000 + (matches * 200);
                }
            }
            
            return { product: p, score };
        }).filter(item => item.score > 0);
        
        if (resultsWithScore.length === 0) {
            resultsContainer.innerHTML = '<p class="empty-state">Ничего не найдено</p>';
            return;
        }
        
        // Сортировка по баллам (от большего к меньшему)
        resultsWithScore.sort((a, b) => b.score - a.score);
        const results = resultsWithScore.map(item => item.product);
        
        // Группировка по брендам
        const brandGroups = {};
        results.forEach(p => {
            const brand = p.brand || 'Без бренда';
            if (!brandGroups[brand]) {
                brandGroups[brand] = [];
            }
            brandGroups[brand].push(p);
        });
        
        // Сортировка брендов
        const sortedBrands = Object.keys(brandGroups).sort();
        
        // Генерация HTML с кнопками показать/скрыть
        const html = sortedBrands.map((brand, brandIndex) => {
            const brandProducts = brandGroups[brand];
            const showMoreNeeded = brandProducts.length > 3;
            
            // Показываем первые 3 товара
            const visibleProducts = brandProducts.slice(0, 3);
            const hiddenProducts = showMoreNeeded ? brandProducts.slice(3) : [];
            
            const visibleHtml = visibleProducts.map(p => components.productCard(p)).join('');
            const hiddenHtml = hiddenProducts.map(p => components.productCard(p)).join('');
            
            return `
                <div class="brand-group" data-brand="${brand}">
                    <div class="brand-header">
                        <h3 class="brand-name">${brand}</h3>
                        <span class="brand-count">${brandProducts.length} товар(ов)</span>
                    </div>
                    <div class="products-grid brand-products-${brandIndex}">
                        ${visibleHtml}
                        ${showMoreNeeded ? `<div class="products-hidden" style="display: none;">${hiddenHtml}</div>` : ''}
                    </div>
                    ${showMoreNeeded ? `
                        <button class="btn-show-more" data-brand-index="${brandIndex}" data-expanded="false">
                            <i class="ph ph-caret-down"></i>
                            <span>Показать ещё ${hiddenProducts.length}</span>
                        </button>
                    ` : ''}
                </div>
            `;
        }).join('');

        resultsContainer.innerHTML = html;
        
        // Добавляем обработчики для кнопок "Показать ещё"
        document.querySelectorAll('.btn-show-more').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const button = e.currentTarget;
                const brandIndex = button.dataset.brandIndex;
                const isExpanded = button.dataset.expanded === 'true';
                const hiddenDiv = document.querySelector(`.brand-products-${brandIndex} .products-hidden`);
                
                if (isExpanded) {
                    // Скрыть
                    hiddenDiv.style.display = 'none';
                    button.dataset.expanded = 'false';
                    button.innerHTML = `
                        <i class="ph ph-caret-down"></i>
                        <span>Показать ещё ${hiddenDiv.children.length}</span>
                    `;
                } else {
                    // Показать
                    hiddenDiv.style.display = 'contents';
                    button.dataset.expanded = 'true';
                    button.innerHTML = `
                        <i class="ph ph-caret-up"></i>
                        <span>Скрыть</span>
                    `;
                }
            });
        });
        
        this.attachEventListeners();
    },

    async handlePromocode() {
        const input = document.getElementById('promocodeInput');
        if (!input) return;
        
        const code = input.value.trim();
        if (!code) {
            utils.showToast('Введите промокод', 'error');
            return;
        }
        
        utils.showLoader();
        
        try {
            const result = await api.applyPromocode(code);
            
            if (result.success) {
                utils.showToast(`✅ Промокод применён!`);
                input.value = '';
                
                // Обновляем данные пользователя
                await dataManager.loadAll();
                
                // Принудительно перерисовать страницу профиля
                navigation.goTo('profile');
            } else {
                utils.showToast(result.error || 'Неверный промокод', 'error');
            }
        } catch (error) {
            utils.showToast('Ошибка применения промокода', 'error');
            utils.log('Promocode error', error);
        } finally {
            utils.hideLoader();
        }
    },
    
    updateCartTotal() {
        const subtotal = cart.getTotal();
        const autoDiscount = state.autoDiscounts?.total_discount || 0;
        const afterDiscount = subtotal - autoDiscount;
        
        const toggleBalanceBtn = document.getElementById('toggleBalanceBtn');
        const useBalance = toggleBalanceBtn?.dataset.active === 'true';
        
        let balanceUsed = 0;
        if (useBalance && state.user) {
            const availableBalance = state.user.balance || 0;
            // Баланс применяется к сумме ПОСЛЕ автоматических скидок
            balanceUsed = Math.min(availableBalance, afterDiscount);
        }
        
        const total = Math.max(0, afterDiscount - balanceUsed);
        
        // Обновить UI
        const cartTotalEl = document.getElementById('cartTotal');
        const balanceUsedRow = document.getElementById('balanceUsedRow');
        const balanceUsedAmount = document.getElementById('balanceUsedAmount');
        
        // Обновить итоговую сумму
        if (cartTotalEl) {
            cartTotalEl.textContent = utils.formatPrice(total);
        }
        
        // Показать/скрыть строку использованного баланса
        if (balanceUsedRow && balanceUsedAmount) {
            if (balanceUsed > 0) {
                balanceUsedRow.style.display = 'flex';
                balanceUsedAmount.textContent = `-${utils.formatPrice(balanceUsed)}`;
            } else {
                balanceUsedRow.style.display = 'none';
            }
        }
        
        utils.log('Cart total updated:', { 
            subtotal, 
            autoDiscount, 
            afterDiscount, 
            balanceUsed, 
            total 
        });
    },

    attachEventListeners() {
        // Кнопка использования баланса в корзине
        const toggleBalanceBtn = document.getElementById('toggleBalanceBtn');
        if (toggleBalanceBtn) {
            toggleBalanceBtn.addEventListener('click', (e) => {
                e.preventDefault();
                const isActive = toggleBalanceBtn.dataset.active === 'true';
                toggleBalanceBtn.dataset.active = !isActive ? 'true' : 'false';
                
                // Обновить UI
                if (!isActive) {
                    toggleBalanceBtn.classList.add('active');
                } else {
                    toggleBalanceBtn.classList.remove('active');
                }
                
                // Обновить итоговую сумму
                this.updateCartTotal();
            });
        }
        
        // Слайдеры изображений в карточках товаров
        document.querySelectorAll('.product-image-slider').forEach(slider => {
            const dots = slider.querySelectorAll('.slider-dot');
            const images = slider.querySelectorAll('img');
            
            if (images.length > 1) {
                let autoSlideInterval;
                let touchStartX = 0;
                let touchEndX = 0;
                
                const goToSlide = (index) => {
                    images.forEach(img => img.classList.remove('active'));
                    dots.forEach(dot => dot.classList.remove('active'));
                    
                    images[index].classList.add('active');
                    if (dots[index]) dots[index].classList.add('active');
                };
                
                // Автопрокрутка каждые 10 секунд
                const startAutoSlide = () => {
                    autoSlideInterval = setInterval(() => {
                        const currentIndex = parseInt(slider.querySelector('img.active').dataset.index);
                        const nextIndex = (currentIndex + 1) % images.length;
                        goToSlide(nextIndex);
                    }, 10000);
                };
                
                const stopAutoSlide = () => {
                    if (autoSlideInterval) clearInterval(autoSlideInterval);
                };
                
                // Свайп для переключения
                slider.addEventListener('touchstart', (e) => {
                    touchStartX = e.touches[0].clientX;
                }, { passive: true });
                
                slider.addEventListener('touchend', (e) => {
                    touchEndX = e.changedTouches[0].clientX;
                    handleSwipe();
                }, { passive: true });
                
                const handleSwipe = () => {
                    const swipeThreshold = 50;
                    const diff = touchStartX - touchEndX;
                    
                    if (Math.abs(diff) > swipeThreshold) {
                        const currentIndex = parseInt(slider.querySelector('img.active').dataset.index);
                        let newIndex;
                        
                        if (diff > 0) {
                            // Свайп влево - следующее изображение
                            newIndex = (currentIndex + 1) % images.length;
                        } else {
                            // Свайп вправо - предыдущее изображение
                            newIndex = (currentIndex - 1 + images.length) % images.length;
                        }
                        
                        goToSlide(newIndex);
                        stopAutoSlide();
                        startAutoSlide();
                    }
                };
                
                // Клик по точкам
                dots.forEach(dot => {
                    dot.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const index = parseInt(dot.dataset.index);
                        goToSlide(index);
                        stopAutoSlide();
                        startAutoSlide();
                    });
                });
                
                // Запустить автопрокрутку
                startAutoSlide();
                
                // Остановить при удалении карточки
                slider.addEventListener('destroyed', stopAutoSlide);
            }
        });
        
        // Карточки товаров - открытие модального окна
        document.querySelectorAll('.product-card').forEach(card => {
            card.addEventListener('click', (e) => {
                // Если клик по кнопке избранного или точкам слайдера, игнорируем
                if (e.target.closest('.favorite-btn') || e.target.closest('.slider-dot')) return;
                
                const productId = parseInt(card.dataset.productId);
                const product = state.products.find(p => p.id === productId);
                if (product) {
                    productModal.show(product);
                }
            });
        });

        // Категории
        document.querySelectorAll('[data-category-id]').forEach(el => {
            el.addEventListener('click', (e) => {
                const categoryId = e.currentTarget.dataset.categoryId;
                this.goTo('category', { currentCategoryId: categoryId });
            });
        });

        // Избранное (checkbox)
        document.querySelectorAll('.favorite-checkbox').forEach(checkbox => {
            // Удаляем старые обработчики чтобы избежать дублирования
            const oldHandler = checkbox._favoriteHandler;
            if (oldHandler) {
                checkbox.removeEventListener('change', oldHandler);
            }
            
            const handler = async (e) => {
                e.stopPropagation();
                e.preventDefault();
                
                const variantId = parseInt(checkbox.dataset.variantId);
                const productId = parseInt(checkbox.dataset.productId);
                
                // Сохраняем текущее состояние
                const currentState = checkbox.checked;
                
                const result = await favorites.toggle(variantId, productId);
                
                if (result) {
                    // Обновляем состояние checkbox на основе реального состояния
                    const isFav = favorites.isFavorite(variantId);
                    checkbox.checked = isFav;
                } else {
                    // Если ошибка, возвращаем предыдущее состояние
                    checkbox.checked = currentState;
                }
            };
            
            checkbox._favoriteHandler = handler;
            checkbox.addEventListener('change', handler);
        });

        // Количество в корзине
        document.querySelectorAll('.quantity-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const variantId = parseInt(btn.dataset.variantId);
                const action = btn.dataset.action;
                const delta = action === 'increase' ? 1 : -1;
                cart.updateQuantity(variantId, delta);
            });
        });

        // Удалить из корзины
        document.querySelectorAll('.remove-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const variantId = parseInt(btn.dataset.variantId);
                cart.remove(variantId);
            });
        });

        // Оформить заказ
        const checkoutBtn = document.getElementById('checkoutBtn');
        if (checkoutBtn) {
            checkoutBtn.addEventListener('click', () => {
                // Получить состояние кнопки баланса из корзины
                const toggleBalanceBtn = document.getElementById('toggleBalanceBtn');
                const useBalanceInCart = toggleBalanceBtn?.dataset.active === 'true';
                
                checkout.show(useBalanceInCart);
            });
        }
        
        // Кнопки "Показать ещё" для брендов
        document.querySelectorAll('.btn-show-more').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const brandIndex = btn.dataset.brandIndex;
                const hiddenContainer = document.querySelector(`.brand-products-hidden-${brandIndex}`);
                
                if (hiddenContainer) {
                    const isVisible = hiddenContainer.style.display !== 'none';
                    
                    if (isVisible) {
                        // Скрыть
                        hiddenContainer.style.display = 'none';
                        btn.innerHTML = '<i class="ph ph-caret-down"></i> Показать ещё ' + hiddenContainer.querySelectorAll('.product-card').length;
                    } else {
                        // Показать
                        hiddenContainer.style.display = 'grid';
                        btn.innerHTML = '<i class="ph ph-caret-up"></i> Скрыть';
                        
                        // Перерисовать обработчики для новых карточек
                        this.attachEventListeners();
                    }
                }
            });
        });
    }
};

// ======================
// PAYMENT HELPERS (Global)
// ======================
const app = {
    currentPaymentMethod: null,
    currentPaymentData: null,
    currentOrderId: null,
    
    copyPaymentData() {
        console.log('copyPaymentData called');
        // Получить данные из DOM элементов
        const cardNumber = document.getElementById('cardNumberDisplay')?.textContent?.replace(/\s/g, '');
        const phoneNumber = document.getElementById('phoneNumberDisplay')?.textContent;
        
        console.log('Payment data found:', { cardNumber, phoneNumber });
        
        if (cardNumber && cardNumber !== '') {
            this.copyToClipboard(cardNumber, 'Номер карты скопирован!');
        } else if (phoneNumber && phoneNumber !== '') {
            this.copyToClipboard(phoneNumber, 'Номер телефона скопирован!');
        } else {
            console.error('No payment data found to copy');
        }
    },
    
    copyOrderComment() {
        if (!this.currentOrderId) return;
        const comment = `Заказ #${this.currentOrderId}`;
        this.copyToClipboard(comment, 'Комментарий скопирован!');
    },
    
    copyToClipboard(text, successMessage) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text)
                .then(() => utils.showToast(successMessage || 'Скопировано!'))
                .catch(err => {
                    console.error('Clipboard API failed:', err);
                    this.fallbackCopy(text, successMessage);
                });
        } else {
            this.fallbackCopy(text, successMessage);
        }
    },
    
    fallbackCopy(text, successMessage) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        
        try {
            textarea.select();
            textarea.setSelectionRange(0, 99999);
            const success = document.execCommand('copy');
            if (success) {
                utils.showToast(successMessage || 'Скопировано!');
            } else {
                utils.showToast('Не удалось скопировать', 'error');
            }
        } catch (err) {
            console.error('Copy failed:', err);
            utils.showToast('Не удалось скопировать', 'error');
        } finally {
            document.body.removeChild(textarea);
        }
    },
    
    async loadPaymentSettings(orderId, totalAmount) {
        try {
            const response = await fetch(`/api/orders/${orderId}/payment-info`, {
                headers: {
                    'X-Telegram-User-Id': state.telegramUserId ? state.telegramUserId.toString() : ''
                }
            });
            
            if (!response.ok) {
                console.error('Failed to load payment settings');
                return;
            }
            
            const data = await response.json();
            
            if (data.success) {
                console.log('Payment settings loaded:', data);
                this.currentOrderId = orderId;
                this.currentPaymentMethod = data.payment_method;
                this.currentPaymentData = data.payment_method === 'card' 
                    ? data.card_number.replace(/\s/g, '') 
                    : data.phone_number;
                
                const cardBlock = document.getElementById('cardPaymentBlock');
                const phoneBlock = document.getElementById('phonePaymentBlock');
                const instructionText = document.getElementById('paymentInstructionText');
                const step2 = document.getElementById('paymentStep2');
                const step3 = document.getElementById('paymentStep3');
                
                console.log('DOM elements found:', {
                    cardBlock: !!cardBlock,
                    phoneBlock: !!phoneBlock,
                    instructionText: !!instructionText
                });
                
                if (data.payment_method === 'card') {
                    console.log('Setting up card payment:', data.card_number);
                    
                    if (cardBlock) {
                        cardBlock.style.display = 'block';
                        cardBlock.style.visibility = 'visible';
                        cardBlock.style.opacity = '1';
                        console.log('Card block shown');
                        console.log('Card block computed style:', window.getComputedStyle(cardBlock).display);
                    }
                    if (phoneBlock) {
                        phoneBlock.style.display = 'none';
                        console.log('Phone block hidden');
                    }
                    
                    const cardNumberEl = document.getElementById('cardNumberDisplay');
                    const cardBankEl = document.getElementById('cardBankDisplay');
                    const cardHolderEl = document.getElementById('cardHolderDisplay');
                    
                    if (cardNumberEl) {
                        cardNumberEl.textContent = data.card_number;
                        console.log('Card number set:', cardNumberEl.textContent);
                        console.log('Card number element visible:', cardNumberEl.offsetParent !== null);
                    } else {
                        console.error('Card number element not found!');
                    }
                    if (cardBankEl) {
                        cardBankEl.textContent = data.card_bank || '';
                        console.log('Card bank set:', cardBankEl.textContent);
                    }
                    if (cardHolderEl) {
                        cardHolderEl.textContent = data.card_holder || '';
                        console.log('Card holder set:', cardHolderEl.textContent);
                    }
                    
                    if (instructionText) instructionText.textContent = '💳 Оплатите заказ переводом на карту';
                    if (step2) step2.textContent = 'Выберите "Переводы" → "На карту другого банка"';
                    if (step3) step3.textContent = 'Нажмите кнопку "Копировать" рядом с номером карты и вставьте его';
                } else if (data.payment_method === 'phone') {
                    console.log('Setting up phone payment:', data.phone_number);
                    
                    if (cardBlock) {
                        cardBlock.style.display = 'none';
                        console.log('Card block hidden');
                    }
                    if (phoneBlock) {
                        phoneBlock.style.display = 'block';
                        console.log('Phone block shown');
                    }
                    
                    const phoneNumberEl = document.getElementById('phoneNumberDisplay');
                    if (phoneNumberEl) {
                        phoneNumberEl.textContent = data.phone_number;
                        console.log('Phone number set:', phoneNumberEl.textContent);
                    }
                    
                    if (instructionText) instructionText.textContent = '📱 Оплатите заказ через СБП';
                    if (step2) step2.textContent = 'Выберите "Переводы" → "По номеру телефона" или "СБП"';
                    if (step3) step3.textContent = 'Нажмите кнопку "Копировать" рядом с номером и вставьте его';
                }
                
                const amountEl = document.getElementById('paymentAmountInstruction');
                const commentEl = document.getElementById('paymentCommentInstruction');
                if (amountEl) amountEl.textContent = `${totalAmount}₽`;
                if (commentEl) commentEl.textContent = `Заказ #${orderId}`;
            } else {
                console.error('Failed to load payment settings:', data);
            }
        } catch (error) {
            console.error('Error loading payment settings:', error);
        }
    }
};

// Сделать app доступным глобально
window.app = app;

// ======================
// CHECKOUT
// ======================
const checkout = {
    appliedPromo: null,
    promoDiscount: 0,
    
    show(useBalanceFromCart = false) {
        const modal = document.getElementById('checkoutModal');
        if (!modal) return;
        
        modal.classList.remove('hidden');
        
        // Генерация дат самовывоза
        this.populatePickupDates();
        
        // Сброс промокода
        this.appliedPromo = null;
        this.promoDiscount = 0;
        
        // Установить checkbox баланса из корзины и добавить обработчики
        const useBalanceCheckbox = document.getElementById('useBalance');
        if (useBalanceCheckbox) {
            useBalanceCheckbox.checked = useBalanceFromCart;
            useBalanceCheckbox.removeEventListener('change', this.updateSummary.bind(this));
            useBalanceCheckbox.addEventListener('change', this.updateSummary.bind(this));
        }
        
        // Тип доставки всегда "pickup" (самовывоз)
        // Показываем все поля самовывоза
        const pickupGroup = document.getElementById('pickupLocationGroup');
        const pickupDateGroup = document.getElementById('pickupDateGroup');
        const pickupTimeGroup = document.getElementById('pickupTimeGroup');
        
        if (pickupGroup) pickupGroup.classList.remove('hidden');
        if (pickupDateGroup) pickupDateGroup.classList.remove('hidden');
        if (pickupTimeGroup) pickupTimeGroup.classList.remove('hidden');
        
        const submitBtn = document.getElementById('submitOrder');
        if (submitBtn) {
            // Удаляем все старые обработчики через замену элемента
            const newBtn = submitBtn.cloneNode(true);
            submitBtn.parentNode.replaceChild(newBtn, submitBtn);
            newBtn.addEventListener('click', this.submit.bind(this));
        }
        
        const closeBtn = document.getElementById('closeCheckout');
        if (closeBtn) {
            closeBtn.removeEventListener('click', () => modal.classList.add('hidden'));
            closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
        }
        
        // Промокод кнопка
        const applyPromoBtn = document.getElementById('applyCheckoutPromo');
        if (applyPromoBtn) {
            applyPromoBtn.removeEventListener('click', this.applyPromocode.bind(this));
            applyPromoBtn.addEventListener('click', this.applyPromocode.bind(this));
        }
        
        // Обновить доступный баланс
        const availableBalanceEl = document.getElementById('availableBalance');
        if (availableBalanceEl && state.user) {
            availableBalanceEl.textContent = Math.floor(state.user.balance || 0);
        }
        
        this.updateSummary();
    },

    populatePickupDates() {
        const pickupDateSelect = document.getElementById('pickupDate');
        if (!pickupDateSelect) return;
        
        // Очистить существующие опции (кроме placeholder)
        pickupDateSelect.innerHTML = '<option value="">Выберите дату</option>';
        
        const today = new Date();
        const dayNames = ['сегодня', 'завтра', 'послезавтра', 'через 3 дня', 'через 4 дня', 
                         'через 5 дней', 'через 6 дней', 'через 7 дней', 'через 8 дней', 'через 9 дней'];
        
        for (let i = 0; i < 10; i++) {
            const date = new Date(today);
            date.setDate(today.getDate() + i);
            
            const day = String(date.getDate()).padStart(2, '0');
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const dateStr = `${day}.${month}`;
            
            const label = `${dayNames[i]} (${dateStr})`;
            const value = `${day}.${month}.${date.getFullYear()}`;
            
            // Добавляем эмодзи для первых дней
            let emoji = '';
            if (i === 0) emoji = '📅 ';
            else if (i === 1) emoji = '🗓️ ';
            else if (i === 2) emoji = '📆 ';
            
            const option = document.createElement('option');
            option.value = value;
            option.textContent = emoji + label;
            pickupDateSelect.appendChild(option);
        }
        
        // Инициализировать кастомные дропдауны
        this.initCustomSelects();
    },

    initCustomSelects() {
        const selectIds = ['pickupLocation', 'pickupDate', 'pickupTime', 'paymentMethod'];
        
        selectIds.forEach(id => {
            const select = document.getElementById(id);
            if (!select) return;
            
            const formGroup = select.closest('.form-group');
            if (!formGroup) return;
            
            // Удалить старые кастомные элементы если есть
            const oldDropdown = formGroup.querySelector('.custom-select-dropdown');
            const oldTrigger = formGroup.querySelector('.custom-select-trigger');
            if (oldDropdown) oldDropdown.remove();
            if (oldTrigger) oldTrigger.remove();
            
            // Создать триггер-кнопку
            const trigger = document.createElement('div');
            trigger.className = 'custom-select-trigger';
            const selectedOption = select.options[select.selectedIndex];
            trigger.textContent = selectedOption?.textContent || 'Выберите...';
            
            // Добавить класс placeholder если выбрана пустая опция
            if (!selectedOption?.value) {
                trigger.classList.add('placeholder');
            }
            
            // Создать кастомный дропдаун
            const dropdown = document.createElement('div');
            dropdown.className = 'custom-select-dropdown';
            
            // Добавить опции
            Array.from(select.options).forEach((option, index) => {
                const optionDiv = document.createElement('div');
                optionDiv.className = 'custom-select-option';
                if (!option.value) optionDiv.classList.add('placeholder');
                if (option.selected) optionDiv.classList.add('selected');
                
                optionDiv.textContent = option.textContent;
                optionDiv.dataset.value = option.value;
                optionDiv.dataset.index = index;
                
                optionDiv.addEventListener('click', () => {
                    // Обновить select
                    select.selectedIndex = index;
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    
                    // Обновить текст триггера
                    trigger.textContent = option.textContent;
                    
                    // Обновить класс placeholder
                    if (option.value) {
                        trigger.classList.remove('placeholder');
                    } else {
                        trigger.classList.add('placeholder');
                    }
                    
                    // Обновить визуально выбранную опцию
                    dropdown.querySelectorAll('.custom-select-option').forEach(opt => {
                        opt.classList.remove('selected');
                    });
                    optionDiv.classList.add('selected');
                    
                    // Закрыть дропдаун
                    dropdown.classList.remove('show');
                });
                
                dropdown.appendChild(optionDiv);
            });
            
            formGroup.appendChild(trigger);
            formGroup.appendChild(dropdown);
            
            // Открытие/закрытие по клику на триггер
            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                
                // Закрыть все другие дропдауны
                document.querySelectorAll('.custom-select-dropdown.show').forEach(dd => {
                    if (dd !== dropdown) dd.classList.remove('show');
                });
                
                // Переключить текущий
                dropdown.classList.toggle('show');
            });
        });
        
        // Закрытие дропдаунов при клике вне
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.custom-select-trigger') && !e.target.closest('.custom-select-dropdown')) {
                document.querySelectorAll('.custom-select-dropdown.show').forEach(dd => {
                    dd.classList.remove('show');
                });
            }
        });
    },

    handleDeliveryChange(e) {
        const type = e.target.value;
        const pickupGroup = document.getElementById('pickupLocationGroup');
        const pickupDateGroup = document.getElementById('pickupDateGroup');
        const pickupTimeGroup = document.getElementById('pickupTimeGroup');
        const deliveryGroup = document.getElementById('deliveryAddressGroup');
        
        if (type === 'pickup') {
            pickupGroup?.classList.remove('hidden');
            pickupDateGroup?.classList.remove('hidden');
            pickupTimeGroup?.classList.remove('hidden');
            deliveryGroup?.classList.add('hidden');
        } else {
            pickupGroup?.classList.add('hidden');
            pickupDateGroup?.classList.add('hidden');
            pickupTimeGroup?.classList.add('hidden');
            deliveryGroup?.classList.remove('hidden');
        }
        
        this.updateSummary();
    },
    
    async applyPromocode() {
        const input = document.getElementById('checkoutPromoInput');
        const resultEl = document.getElementById('checkoutPromoResult');
        const code = input?.value?.trim();
        
        if (!code) {
            utils.showToast('Введите промокод', 'error');
            return;
        }
        
        try {
            // Валидация промокода (только для скидки, не balance)
            const result = await api.request('/api/promocode/validate', {
                method: 'POST',
                body: JSON.stringify({ 
                    code: code,
                    expected_type: 'discount' // только скидочные промокоды
                })
            });
            
            if (result.valid && (result.type === 'percent' || result.type === 'rub')) {
                this.appliedPromo = result;
                
                // Вычислить скидку
                const subtotal = cart.getTotal();
                if (result.type === 'percent') {
                    this.promoDiscount = Math.floor((subtotal * result.value) / 100);
                } else {
                    this.promoDiscount = Math.min(result.value, subtotal);
                }
                
                resultEl.style.display = 'block';
                resultEl.textContent = `✅ Промокод применён! Скидка: ${utils.formatPrice(this.promoDiscount)}`;
                utils.showToast('Промокод применён');
                
                this.updateSummary();
            } else {
                utils.showToast('Этот промокод не для скидки на заказ', 'error');
            }
        } catch (error) {
            utils.log('Promo validation error', error);
            utils.showToast('Неверный промокод', 'error');
        }
    },

    updateSummary() {
        const subtotal = cart.getTotal();
        const deliveryCost = 0; // Всегда самовывоз, стоимость доставки = 0
        
        // Применяем автоматические скидки + промокод
        const autoDiscount = state.autoDiscounts?.total_discount || 0;
        let discount = autoDiscount + this.promoDiscount;
        
        // Применяем баланс если выбрано
        const useBalance = document.getElementById('useBalance')?.checked;
        let balanceUsed = 0;
        if (useBalance && state.user) {
            const availableBalance = state.user.balance || 0;
            const totalBeforeBalance = subtotal + deliveryCost - discount;
            balanceUsed = Math.min(availableBalance, totalBeforeBalance);
        }
        
        const total = Math.max(0, subtotal + deliveryCost - discount - balanceUsed);
        
        // Рассчитываем кешбек ТОЛЬКО если есть реальная оплата (не только балансом)
        // Если оплачено полностью балансом (total = 0), кешбек не начисляется
        const cashbackAmount = total > 0 ? cart.calculateCashback() : 0;
        
        utils.log('Checkout summary update:', {
            subtotal,
            deliveryCost,
            autoDiscount,
            promoDiscount: this.promoDiscount,
            totalDiscount: discount,
            balanceUsed,
            total,
            cashbackAmount,
            cartItems: state.cart.length
        });
        
        // Обновляем UI
        const subtotalEl = document.getElementById('checkoutSubtotal');
        const deliveryEl = document.getElementById('checkoutDelivery');
        const discountEl = document.getElementById('checkoutDiscount');
        const discountRow = document.getElementById('discountRow');
        const balanceEl = document.getElementById('checkoutBalanceUsed');
        const balanceRow = document.getElementById('balanceRow');
        const cashbackEl = document.getElementById('checkoutCashback');
        const cashbackRow = document.getElementById('cashbackRow');
        const totalEl = document.getElementById('checkoutTotal');
        
        if (subtotalEl) subtotalEl.textContent = utils.formatPrice(subtotal);
        if (deliveryEl) deliveryEl.textContent = deliveryCost === 0 ? '0₽' : utils.formatPrice(deliveryCost);
        
        // Показать/скрыть строку скидки
        if (discount > 0) {
            discountRow.style.display = 'flex';
            // Формируем текст с деталями скидки
            let discountText = '-' + utils.formatPrice(discount);
            if (autoDiscount > 0 && this.promoDiscount > 0) {
                discountText += ` (🎁 ${utils.formatPrice(autoDiscount)} + 🎟️ ${utils.formatPrice(this.promoDiscount)})`;
            } else if (autoDiscount > 0) {
                discountText += ' 🎁';
            } else if (this.promoDiscount > 0) {
                discountText += ' 🎟️';
            }
            discountEl.textContent = discountText;
        } else {
            discountRow.style.display = 'none';
        }
        
        // Показать/скрыть строку баланса
        if (balanceUsed > 0) {
            balanceRow.style.display = 'flex';
            balanceEl.textContent = '-' + utils.formatPrice(balanceUsed);
        } else {
            balanceRow.style.display = 'none';
        }
        
        // Показать/скрыть строку кешбека
        if (cashbackAmount > 0) {
            cashbackRow.style.display = 'flex';
            cashbackEl.textContent = '+' + utils.formatPrice(cashbackAmount);
        } else {
            cashbackRow.style.display = 'none';
        }
        
        if (totalEl) totalEl.textContent = utils.formatPrice(total);
    },

    async submit(e) {
        e.preventDefault();
        
        // Защита от двойного клика
        if (this._submitting) {
            utils.log('Already submitting, ignoring duplicate request');
            return;
        }
        this._submitting = true;
        
        const name = document.getElementById('customerName')?.value?.trim();
        const phone = document.getElementById('customerPhone')?.value?.trim();
        const deliveryType = 'pickup'; // Всегда самовывоз
        const paymentMethod = document.getElementById('paymentMethod')?.value;
        
        // Валидация
        if (!name || !phone) {
            utils.showToast('Заполните все обязательные поля', 'error');
            this._submitting = false;
            return;
        }
        
        // Проверка формата телефона
        const phoneRegex = /^\+79\d{9}$/;
        if (!phoneRegex.test(phone)) {
            utils.showToast('Неверный формат телефона. Используйте +79XXXXXXXXX', 'error');
            this._submitting = false;
            return;
        }
        
        // Проверка корзины
        if (state.cart.length === 0) {
            utils.showToast('Корзина пуста', 'error');
            this._submitting = false;
            return;
        }
        
        // Подготовка данных заказа
        const orderData = {
            delivery_type: deliveryType,
            customer_name: name,
            customer_phone: phone,
            payment_method: paymentMethod,
            items: state.cart.map(item => ({
                variant_id: item.variantId,
                quantity: item.quantity,
                price: item.price
            }))
        };
        
        // Добавляем адрес в зависимости от типа доставки
        if (deliveryType === 'pickup') {
            const pickupLocation = document.getElementById('pickupLocation')?.value;
            const pickupDate = document.getElementById('pickupDate')?.value;
            const pickupTime = document.getElementById('pickupTime')?.value;
            
            if (!pickupLocation) {
                utils.showToast('Выберите пункт самовывоза', 'error');
                this._submitting = false;
                return;
            }
            
            if (!pickupDate) {
                utils.showToast('Выберите дату самовывоза', 'error');
                this._submitting = false;
                return;
            }
            
            if (!pickupTime) {
                utils.showToast('Выберите время самовывоза', 'error');
                this._submitting = false;
                return;
            }
            
            orderData.pickup_location = `${pickupLocation} | ${pickupDate} ${pickupTime}`;
        } else {
            const deliveryAddress = document.getElementById('deliveryAddress')?.value?.trim();
            if (!deliveryAddress) {
                utils.showToast('Укажите адрес доставки', 'error');
                this._submitting = false;
                return;
            }
            orderData.delivery_address = deliveryAddress;
        }
        
        // Добавить промокод если применён
        if (this.appliedPromo && this.appliedPromo.code) {
            orderData.promocode = this.appliedPromo.code;
        }
        
        // Добавить флаг использования баланса
        const useBalance = document.getElementById('useBalance')?.checked;
        orderData.use_balance = useBalance || false;
        
        utils.showLoader();
        
        try {
            // ИСПРАВЛЕНО: Полная синхронизация корзины (замена вместо обновления)
            // Это гарантирует, что на сервере будут только актуальные товары
            await api.syncCart(state.cart);
            
            // ВАЖНО: Сохраняем корзину ДО создания заказа (т.к. она будет очищена)
            const cartSnapshot = [...state.cart];
            
            // Теперь создаём заказ (бэкенд возьмёт корзину из БД)
            const result = await api.createOrder(orderData);
            
            if (result.success) {
                // Очистить корзину
                cart.clear();
                
                // Закрыть модал оформления
                document.getElementById('checkoutModal')?.classList.add('hidden');
                
                // Если способ оплаты = СБП онлайн, показать модал подтверждения
                if (paymentMethod === 'sbp_online') {
                    const orderId = result.order_id || result.id;
                    const totalAmount = result.total || this.calculateTotal();
                    
                    utils.hideLoader();
                    
                    // Не показывать модал если сумма = 0
                    if (totalAmount > 0) {
                        this.showPaymentProofModal(orderId, totalAmount);
                    } else {
                        utils.showToast('✅ Заказ успешно оформлен!');
                        // Перезагрузить страницу для полного обновления
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    }
                } else {
                    const orderId = result.order_id || result.id;
                    
                    utils.hideLoader();
                    utils.showToast('✅ Заказ успешно оформлен!');
                    
                    // Редирект к менеджеру с информацией о заказе
                    this.redirectToManager(orderId, orderData, result, cartSnapshot);
                    
                    // Перезагрузить страницу после небольшой задержки
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                }
            } else {
                utils.showToast(result.error || 'Ошибка оформления заказа', 'error');
            }
        } catch (error) {
            utils.log('Checkout error', error);
            
            // Более подробные сообщения об ошибках
            if (error.message.includes('404')) {
                utils.showToast('Ошибка: API недоступен', 'error');
            } else if (error.message.includes('401')) {
                utils.showToast('Ошибка: требуется авторизация', 'error');
            } else if (error.message.includes('500')) {
                utils.showToast('Ошибка сервера. Попробуйте позже', 'error');
            } else {
                utils.showToast('Не удалось оформить заказ. Проверьте соединение', 'error');
            }
        } finally {
            utils.hideLoader();
            this._submitting = false;
        }
    },
    
    calculateTotal() {
        const subtotal = cart.getTotal();
        const deliveryCost = 0; // Всегда самовывоз, стоимость доставки = 0
        
        // Автоматические скидки + промокод
        const autoDiscount = state.autoDiscounts?.total_discount || 0;
        const discount = autoDiscount + this.promoDiscount;
        
        const useBalance = document.getElementById('useBalance')?.checked;
        let balanceUsed = 0;
        if (useBalance && state.user) {
            const availableBalance = state.user.balance || 0;
            const totalBeforeBalance = subtotal + deliveryCost - discount;
            balanceUsed = Math.min(availableBalance, totalBeforeBalance);
        }
        
        return Math.max(0, subtotal + deliveryCost - discount - balanceUsed);
    },
    
    redirectToManager(orderId, orderData, result, cartSnapshot = null) {
        // Формируем детальное сообщение о заказе
        // Используем сохраненную корзину, если передана, иначе текущую
        const cartItems = cartSnapshot || state.cart;
        const itemsList = cartItems.map(item => {
            const name = item.brand || item.name;
            const flavor = item.flavor ? ` (${item.flavor})` : '';
            const price = item.price || 0;
            const quantity = item.quantity || 1;
            const total = price * quantity;
            return `  • ${name}${flavor} - ${quantity} × ${price.toFixed(1)}₽ = ${total.toFixed(1)}₽`;
        }).join('\n');
        
        const deliveryInfo = orderData.delivery_type === 'pickup' 
            ? `📍 Самовывоз: ${orderData.pickup_location}`
            : `🚗 Доставка: ${orderData.delivery_address}`;
        
        const paymentMethodText = 
            orderData.payment_method === 'sbp_online' ? '💳 СБП онлайн' :
            orderData.payment_method === 'sbp_pickup' ? '💳 СБП при получении' :
            orderData.payment_method === 'cash' ? '💵 Наличные' :
            orderData.payment_method === 'balance' ? '💰 Баланс' : 'Не указан';
        
        // Формируем чек
        // Рассчитываем subtotal из cartItems
        const subtotal = result.subtotal || cartItems.reduce((sum, item) => {
            const price = item.price || 0;
            const quantity = item.quantity || 1;
            return sum + (price * quantity);
        }, 0);
        
        const deliveryCost = result.delivery_cost || (orderData.delivery_type === 'delivery' ? CONFIG.DELIVERY_COST : 0);
        const discount = result.discount || 0;
        const balanceUsed = result.balance_used || 0;
        const total = result.total || this.calculateTotal();
        const cashback = result.cashback_earned || 0;
        
        let checkLines = [`  📦 Товары: ${Math.round(subtotal)}₽`];
        
        if (deliveryCost > 0) {
            checkLines.push(`  🚗 Доставка: +${Math.round(deliveryCost)}₽`);
        }
        
        if (discount > 0) {
            checkLines.push(`  🏷️ Скидка: -${Math.round(discount)}₽`);
        }
        
        if (balanceUsed > 0) {
            checkLines.push(`  💰 Баланс: -${Math.round(balanceUsed)}₽`);
        }
        
        checkLines.push('  ━━━━━━━━━━━━━');
        checkLines.push(`  💳 К оплате: ${Math.round(total)}₽`);
        
        if (cashback > 0) {
            checkLines.push(`  💚 Кешбэк: +${Math.round(cashback)}₽`);
        }
        
        const checkText = checkLines.join('\n');
        
        const message = `🎉 Новый заказ #${orderId}\n\n` +
            `👤 Клиент: ${orderData.customer_name}\n` +
            `📱 Телефон: ${orderData.customer_phone}\n\n` +
            `🛍️ Товары:\n${itemsList}\n\n` +
            `💵 Чек:\n${checkText}\n\n` +
            `${deliveryInfo}\n` +
            `💳 Способ оплаты: ${paymentMethodText}`;
        
        // Открываем Telegram с предзаполненным сообщением
        const encodedMessage = encodeURIComponent(message);
        const telegramUrl = `https://t.me/${CONFIG.MANAGER_TELEGRAM.replace('@', '')}?text=${encodedMessage}`;
        
        // Даем время на показ toast, затем открываем Telegram
        setTimeout(() => {
            if (window.Telegram?.WebApp) {
                // В Telegram WebApp используем openTelegramLink
                window.Telegram.WebApp.openTelegramLink(telegramUrl);
            } else {
                // В обычном браузере просто открываем ссылку
                window.open(telegramUrl, '_blank');
            }
        }, 1000);
    },
    
    showPaymentProofModal(orderId, totalAmount) {
        const modal = document.getElementById('paymentProofModal');
        if (!modal) return;
        
        // Заполнить данные
        document.getElementById('paymentOrderNumber').textContent = orderId;
        document.getElementById('paymentAmountDisplay').textContent = utils.formatPrice(totalAmount);
        
        // Обновить номер заказа в назначении платежа
        const purposeNumber = document.getElementById('paymentPurposeNumber');
        if (purposeNumber) {
            purposeNumber.textContent = orderId;
        }
        
        // Обновить инструкцию
        const amountInstruction = document.getElementById('paymentAmountInstruction');
        if (amountInstruction) {
            amountInstruction.textContent = utils.formatPrice(totalAmount);
        }
        
        const commentInstruction = document.getElementById('paymentCommentInstruction');
        if (commentInstruction) {
            commentInstruction.textContent = `Заказ #${orderId}`;
        }
        
        // Загрузить настройки оплаты
        app.loadPaymentSettings(orderId, totalAmount);
        
        // Показать модал
        modal.classList.remove('hidden');
        
        // Обработчик формы
        const form = document.getElementById('paymentProofForm');
        const newForm = form.cloneNode(true);
        form.parentNode.replaceChild(newForm, form);
        
        newForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.submitPaymentProof(orderId);
        });
        
        // Preview скриншота
        const fileInput = document.getElementById('paymentScreenshot');
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const preview = document.getElementById('screenshotPreview');
                    preview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
                };
                reader.readAsDataURL(file);
            }
        });
    },
    
    async submitPaymentProof(orderId) {
        const phone = document.getElementById('paymentPhone')?.value?.trim();
        const fileInput = document.getElementById('paymentScreenshot');
        const file = fileInput?.files[0];
        
        if (!phone || !file) {
            utils.showToast('Заполните все поля', 'error');
            return;
        }
        
        utils.showLoader();
        
        try {
            // Отправка FormData
            const formData = new FormData();
            formData.append('payment_phone', phone);
            formData.append('file', file);
            
            const response = await fetch(`/api/orders/${orderId}/payment-proof`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Telegram-User-Id': state.telegramUserId ? state.telegramUserId.toString() : ''
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                document.getElementById('paymentProofModal')?.classList.add('hidden');
                utils.showToast('✅ Подтверждение оплаты отправлено!');
                
                // Обновляем данные
                await dataManager.loadAll().catch(err => {
                    utils.log('Failed to reload data', err);
                });
                
                // Находим заказ и формируем сообщение для менеджера
                const order = state.orders.find(o => o.id === orderId);
                if (order) {
                    let items = [];
                    try {
                        items = typeof order.items === 'string' ? JSON.parse(order.items) : order.items;
                    } catch (e) {
                        items = [];
                    }
                    
                    const itemsList = items.map(item => 
                        `• ${item.name}${item.flavor ? ' - ' + item.flavor : ''} x${item.quantity} (${utils.formatPrice(item.price * item.quantity)})`
                    ).join('\n');
                    
                    const deliveryInfo = order.delivery_type === 'pickup' 
                        ? `Самовывоз: ${order.pickup_location}`
                        : `Доставка: ${order.delivery_address}`;
                    
                    const message = `✅ Подтверждение оплаты по заказу #${orderId}\n\n` +
                        `📱 Телефон для связи: ${phone}\n` +
                        `💰 Сумма: ${utils.formatPrice(order.total || order.total_amount || 0)}\n\n` +
                        `📦 Товары:\n${itemsList}\n\n` +
                        `🚚 ${deliveryInfo}`;
                    
                    const encodedMessage = encodeURIComponent(message);
                    const telegramUrl = `https://t.me/${CONFIG.MANAGER_TELEGRAM.replace('@', '')}?text=${encodedMessage}`;
                    
                    setTimeout(() => {
                        if (window.Telegram?.WebApp) {
                            window.Telegram.WebApp.openTelegramLink(telegramUrl);
                        } else {
                            window.open(telegramUrl, '_blank');
                        }
                    }, 1000);
                }
            } else {
                utils.showToast(result.error || 'Ошибка отправки', 'error');
            }
        } catch (error) {
            utils.log('Payment proof error', error);
            utils.showToast('Не удалось отправить подтверждение', 'error');
        } finally {
            utils.hideLoader();
        }
    }
};

// ======================
// INITIALIZATION
// ======================
async function init() {
    utils.log('Initializing app...');
    
    // Telegram WebApp
    if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        
        const initData = window.Telegram.WebApp.initDataUnsafe;
        if (initData.user) {
            state.telegramUserId = initData.user.id;
            state.telegramUserData = initData.user;  // Сохраняем все данные пользователя
            utils.log('Telegram User ID:', state.telegramUserId);
            utils.log('Telegram User Data:', state.telegramUserData);
        }
    }
    
    // Проверка авторизации
    if (!state.telegramUserId) {
        if (CONFIG.REQUIRE_AUTH) {
            // Показываем сообщение об ошибке
            document.body.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; padding: 20px; text-align: center;">
                    <i class="ph ph-warning" style="font-size: 64px; color: #ff6b00; margin-bottom: 20px;"></i>
                    <h2 style="margin-bottom: 10px; color: #212121;">Ошибка доступа</h2>
                    <p style="color: #757575; margin-bottom: 20px;">Приложение доступно только через Telegram WebApp</p>
                    <p style="color: #757575; font-size: 14px;">Откройте приложение через бота в Telegram</p>
                </div>
            `;
            utils.hideLoader();
            return;
        }
        // Fallback для разработки (УБЕРИ В ПРОДАКШЕНЕ!)
        state.telegramUserId = 820140184;
    }
    
    // Загрузка данных
    await dataManager.loadAll();
    
    // Проверяем что пользователь существует
    if (CONFIG.REQUIRE_AUTH && (!state.user || !state.user.id)) {
        document.body.innerHTML = `
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; padding: 20px; text-align: center;">
                <i class="ph ph-user-x" style="font-size: 64px; color: #ff6b00; margin-bottom: 20px;"></i>
                <h2 style="margin-bottom: 10px; color: #212121;">Пользователь не найден</h2>
                <p style="color: #757575; margin-bottom: 20px;">Регистрация не удалась. Обновляем страницу...</p>
                <p style="color: #757575; font-size: 14px;">Telegram ID: ${state.telegramUserId}</p>
                <div style="margin-top: 20px;">
                    <div class="loader" style="border: 4px solid #f3f3f3; border-top: 4px solid #ff6b00; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                </div>
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;
        
        // Автоматически обновить страницу через 2 секунды
        setTimeout(() => {
            utils.log('Auto-reloading page due to user not found...');
            window.location.reload();
        }, 2000);
        
        utils.hideLoader();
        return;
    }
    
    // Навигация
    navigation.goTo('home');
    
    // Тема
    const savedTheme = localStorage.getItem('theme') || 'light';
    state.theme = savedTheme;
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    // События навигации
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            navigation.goTo(page);
        });
    });
    
    // Кнопка назад
    const backBtn = document.getElementById('backBtn');
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            navigation.goTo('home');
        });
    }
    
    // Автоматический ввод +7 для полей телефона
    const phoneFields = ['customerPhone', 'paymentPhone'];
    phoneFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            // Установить +7 при фокусе, если поле пустое
            field.addEventListener('focus', function() {
                if (this.value === '') {
                    this.value = '+7';
                }
            });
            
            // Обработка ввода
            field.addEventListener('input', function(e) {
                let value = this.value.replace(/\D/g, ''); // Удалить все нецифровые символы
                
                // Если пользователь удалил +7, вернуть
                if (value.length === 0) {
                    this.value = '+7';
                    return;
                }
                
                // Если начинается с 8, заменить на 7
                if (value[0] === '8') {
                    value = '7' + value.slice(1);
                }
                
                // Убедиться что начинается с 7
                if (value[0] !== '7') {
                    value = '7' + value;
                }
                
                // Ограничить 11 цифрами (7 + 10 цифр номера)
                if (value.length > 11) {
                    value = value.slice(0, 11);
                }
                
                this.value = '+' + value;
            });
            
            // При потере фокуса, если только +7, очистить
            field.addEventListener('blur', function() {
                if (this.value === '+7') {
                    this.value = '';
                }
            });
        }
    });
    
    // Переключатель темы
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const newTheme = state.theme === 'light' ? 'dark' : 'light';
            state.theme = newTheme;
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });
    }
    
    utils.log('App initialized successfully!');
}

// ======================
// ГЛОБАЛЬНЫЕ ФУНКЦИИ ДЛЯ HTML
// ======================
window.closePaymentProofModal = function() {
    document.getElementById('paymentProofModal')?.classList.add('hidden');
};

window.copyMerchantPhone = function() {
    const phone = document.getElementById('merchantPhone')?.textContent;
    if (!phone) return;
    
    // Fallback метод для Telegram WebApp (Clipboard API blocked)
    const textarea = document.createElement('textarea');
    textarea.value = phone;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    
    try {
        textarea.select();
        textarea.setSelectionRange(0, 99999); // Для мобильных
        
        const success = document.execCommand('copy');
        if (success) {
            utils.showToast('✅ Номер скопирован: ' + phone);
        } else {
            utils.showToast('❌ Не удалось скопировать', 'error');
        }
    } catch (err) {
        console.error('Copy failed:', err);
        utils.showToast('❌ Не удалось скопировать', 'error');
    } finally {
        document.body.removeChild(textarea);
    }
};

// Запуск приложения
document.addEventListener('DOMContentLoaded', init);

// Debug в консоль
if (CONFIG.DEBUG) {
    window.hotspotDebug = {
        state,
        utils,
        api,
        navigation,
        cart,
        favorites,
        dataManager,
        productModal,
        quickAddModal,
        checkout,
        CONFIG
    };
}

