# 🚀 Руководство по развертыванию HotSpot Shop

## 📋 Требования

- **Python 3.8+**
- **SQLite3**
- **Nginx** (для продакшена)
- **Systemd** (для автозапуска)
- **SSL сертификат** (Let's Encrypt)

## 🔧 Быстрая установка

### 1. Клонирование и настройка
```bash
git clone https://github.com/your-username/hotspot-shop.git
cd hotspot-shop
pip install -r requirements.txt
```

### 2. Конфигурация
```bash
cp env-example .env
nano .env  # Настройте ваши данные
```

### 3. Инициализация БД
```bash
python init_db.py
```

### 4. Запуск
```bash
python run.py
```

## 🐳 Docker развертывание

### 1. Создание docker-compose.yml
```yaml
version: '3.8'
services:
  hotspot-shop:
    build: .
    ports:
      - "8080:8080"
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - ADMIN_BOT_TOKEN=${ADMIN_BOT_TOKEN}
      - ADMIN_IDS=${ADMIN_IDS}
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### 2. Запуск
```bash
docker-compose up -d
```

## 🌐 Nginx конфигурация

### 1. Создание конфига
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. SSL сертификат
```bash
certbot --nginx -d your-domain.com
```

## 🔄 Systemd сервисы

### 1. Основной бот
```ini
[Unit]
Description=HotSpot Shop Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/hotspot-shop
ExecStart=/usr/bin/python3 run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Активация
```bash
sudo systemctl enable hotspot-bot
sudo systemctl start hotspot-bot
```

## 📊 Мониторинг

### 1. Логи
```bash
# Просмотр логов
journalctl -u hotspot-bot -f

# Логи Nginx
tail -f /var/log/nginx/access.log
```

### 2. Статус сервисов
```bash
systemctl status hotspot-bot
systemctl status nginx
```

## 🔒 Безопасность

### 1. Firewall
```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### 2. Обновления
```bash
# Регулярно обновляйте систему
apt update && apt upgrade -y
```

## 🚨 Резервное копирование

### 1. База данных
```bash
# Создание бэкапа
cp shop.db shop_backup_$(date +%Y%m%d).db

# Автоматический бэкап
0 2 * * * cp /path/to/shop.db /backup/shop_$(date +\%Y\%m\%d).db
```

### 2. Файлы
```bash
tar -czf backup_$(date +%Y%m%d).tar.gz /path/to/hotspot-shop/
```

## 🎯 Оптимизация

### 1. Производительность
- Используйте SSD диски
- Настройте кэширование в Nginx
- Оптимизируйте запросы к БД

### 2. Масштабирование
- Используйте Redis для сессий
- Настройте балансировщик нагрузки
- Рассмотрите PostgreSQL для больших нагрузок

## 📞 Поддержка

При проблемах с развертыванием:
- Создайте Issue в GitHub
- Проверьте логи сервисов
- Убедитесь в правильности конфигурации

---

**Удачного развертывания! 🚀**
