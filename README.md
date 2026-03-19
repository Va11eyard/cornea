# Система заявок на донорскую роговицу

Закрытый веб-портал для врачей-офтальмохирургов — подача заявок на донорскую роговицу.

## Стек

- **Backend**: FastAPI + Jinja2
- **База данных**: SQLite (файл `cornea.db`)
- **Авторизация**: Session middleware (cookie)

---

## Быстрый старт (локально)

```bash
cd cornea_app
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Открыть: http://localhost:8001

**По умолчанию:**
- Логин: `admin`
- Пароль: `admin123`


## Деплой на сервер (Ubuntu, systemd)

### 1. Скопировать файлы

```bash
scp -r cornea_app/ user@SERVER_IP:/opt/cornea_app
```

### 2. Установить зависимости

```bash
cd /opt/cornea_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Поменять секретный ключ

В файле `main.py` найдите строку:
```python
secret_key="cornea-secret-key-change-in-prod-2024"
```
Замените на случайную строку длиной 40+ символов.

### 4. Создать systemd-сервис

```bash
sudo nano /etc/systemd/system/cornea.service
```

```ini
[Unit]
Description=Cornea Requests App
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/cornea_app
ExecStart=/opt/cornea_app/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cornea
sudo systemctl start cornea
```

### 5. Nginx (если уже используется)

```nginx
server {
    listen 80;
    server_name cornea.yourdomain.kz;

    # Запрет индексации
    add_header X-Robots-Tag "noindex, nofollow";

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Для HTTPS добавить certbot:
```bash
sudo certbot --nginx -d cornea.yourdomain.kz
```

---

## Структура проекта

```
cornea_app/
├── main.py                  # FastAPI приложение, маршруты
├── database.py              # SQLite, инициализация БД, модели
├── requirements.txt
├── cornea.db                # База данных (создаётся автоматически)
├── routers/
│   ├── auth.py              # /login, /logout
│   ├── doctor.py            # /doctor/* (врач)
│   └── admin.py             # /admin/* (администратор)
├── templates/
│   ├── base.html            # Общий layout с навбаром
│   ├── login.html
│   ├── doctor/
│   │   ├── dashboard.html   # Список заявок врача
│   │   ├── request_form.html # Форма новой заявки
│   │   └── request_detail.html
│   └── admin/
│       ├── dashboard.html   # Все заявки + фильтры
│       ├── request_detail.html # Просмотр + смена статуса + копирование
│       ├── users.html       # Управление врачами
│       └── options.html     # Варианты обработки тканей
└── static/
    ├── css/main.css
    └── js/main.js
```

---

## Роли

| Роль | Возможности |
|------|------------|
| `doctor` | Создавать заявки, просматривать только свои |
| `admin` | Видеть все заявки, менять статус, удалять, скачивать CSV, управлять врачами и настройками |

---

## Статусы заявки

| Статус | Описание |
|--------|----------|
| `новая` | Только что создана врачом |
| `отправлена` | Перенесена в One World Sight Alliance |
| `выполнена` | Запрос выполнен |

---

## Функция «Скопировать заявку»

На странице заявки (для администратора) кнопка **«Скопировать заявку»** копирует все поля в буфер обмена в форматированном виде — для быстрой вставки в форму One World Sight Alliance.

---

## Безопасность

- ✅ Доступ только по логину/паролю
- ✅ Страницы не индексируются (`noindex, nofollow`)
- ✅ ФИО пациента не хранится — только код пациента
- ✅ Пароли хранятся в виде SHA-256 хешей
- ✅ Врач не видит заявки других врачей
- ⚠️ Для продакшена: обязательно HTTPS + смените `secret_key`
