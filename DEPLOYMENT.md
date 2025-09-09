# 🚀 Руководство по деплою Friendly Loan

## 📋 Варианты деплоя

### 1. 🐳 Docker (Рекомендуется)

#### Быстрый старт
```bash
# Клонируйте репозиторий
git clone <repository-url>
cd friendly-loan

# Скопируйте файл окружения
cp env.example .env

# Отредактируйте .env файл
nano .env

# Запустите деплой
chmod +x deploy-docker.sh
./deploy-docker.sh
```

#### Ручной запуск
```bash
# Создайте .env файл
cp env.example .env

# Сгенерируйте SSL сертификаты
mkdir -p ssl
openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Запустите контейнеры
docker-compose up -d

# Проверьте статус
docker-compose ps
```

### 2. 🐧 Системный деплой (Ubuntu/Debian)

#### Автоматический деплой
```bash
# Запустите скрипт деплоя
sudo chmod +x deploy.sh
sudo ./deploy.sh
```

#### Ручной деплой
```bash
# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите зависимости
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# Создайте директорию приложения
sudo mkdir -p /opt/friendly-loan
cd /opt/friendly-loan

# Скопируйте файлы приложения
sudo cp -r /path/to/friendly-loan/* .

# Создайте виртуальное окружение
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt

# Настройте права доступа
sudo chown -R www-data:www-data /opt/friendly-loan
sudo chmod -R 755 /opt/friendly-loan

# Настройте systemd сервис
sudo cp friendly-loan.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable friendly-loan
sudo systemctl start friendly-loan

# Настройте Nginx
sudo cp nginx.conf /etc/nginx/sites-available/friendly-loan
sudo ln -s /etc/nginx/sites-available/friendly-loan /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# Настройте SSL (опционально)
sudo certbot --nginx -d your-domain.com
```

## 🔧 Конфигурация

### Переменные окружения

Создайте файл `.env` на основе `env.example`:

```bash
# Environment
FLASK_ENV=production

# Security (ОБЯЗАТЕЛЬНО измените!)
SECRET_KEY=your-super-secret-key-change-this-in-production

# Database
DATABASE_URL=sqlite:///loans.db

# Redis (опционально)
REDIS_URL=redis://localhost:6379/0

# Upload settings
UPLOAD_FOLDER=static/uploads

# Logging
LOG_LEVEL=INFO
LOG_FILE=app.log

# Server settings
HOST=0.0.0.0
PORT=8000
WORKERS=4
```

### SSL сертификаты

#### Для разработки
```bash
mkdir -p ssl
openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

#### Для продакшена
```bash
# Используйте Let's Encrypt
sudo certbot --nginx -d your-domain.com
```

## 📊 Мониторинг

### Логи
```bash
# Docker
docker-compose logs -f web

# Systemd
sudo journalctl -u friendly-loan -f

# Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Health Check
```bash
curl http://localhost/health
```

### Статус сервисов
```bash
# Docker
docker-compose ps

# Systemd
sudo systemctl status friendly-loan
sudo systemctl status nginx
```

## 🔒 Безопасность

### Обязательные настройки для продакшена

1. **Измените SECRET_KEY**
2. **Настройте HTTPS**
3. **Ограничьте доступ к базе данных**
4. **Настройте файрвол**
5. **Регулярно обновляйте зависимости**

### Файрвол (UFW)
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Обновление приложения
```bash
# Docker
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Systemd
git pull
sudo systemctl stop friendly-loan
sudo venv/bin/pip install -r requirements.txt
sudo systemctl start friendly-loan
```

## 🐛 Отладка

### Проблемы с Docker
```bash
# Проверьте логи
docker-compose logs web

# Перезапустите контейнеры
docker-compose restart

# Пересоберите образы
docker-compose build --no-cache
```

### Проблемы с systemd
```bash
# Проверьте статус
sudo systemctl status friendly-loan

# Проверьте логи
sudo journalctl -u friendly-loan -n 50

# Перезапустите сервис
sudo systemctl restart friendly-loan
```

### Проблемы с Nginx
```bash
# Проверьте конфигурацию
sudo nginx -t

# Перезапустите Nginx
sudo systemctl restart nginx

# Проверьте логи
sudo tail -f /var/log/nginx/error.log
```

## 📈 Масштабирование

### Горизонтальное масштабирование
```yaml
# docker-compose.yml
services:
  web:
    # ... existing config
    deploy:
      replicas: 3
```

### Load Balancer
Используйте Nginx или HAProxy для распределения нагрузки между несколькими экземплярами приложения.

## 🔄 Backup

### База данных
```bash
# SQLite backup
cp loans.db backup/loans-$(date +%Y%m%d-%H%M%S).db

# Автоматический backup
echo "0 2 * * * cp /opt/friendly-loan/loans.db /backup/loans-\$(date +\%Y\%m\%d-\%H\%M\%S).db" | sudo crontab -
```

### Загруженные файлы
```bash
# Backup uploads
tar -czf backup/uploads-$(date +%Y%m%d-%H%M%S).tar.gz static/uploads/
```

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи
2. Убедитесь, что все сервисы запущены
3. Проверьте конфигурацию
4. Обратитесь к документации

---

**Версия:** 1.0.0  
**Последнее обновление:** 2025
