# Система заявок на донорскую роговицу

Закрытый веб-портал для врачей-офтальмохирургов — подача заявок на донорскую роговицу.

## Стек

- **Backend**: FastAPI + Jinja2
- **База данных**: SQLite (файл `cornea.db`)
- **Авторизация**: Session middleware (cookie)

---

## Быстрый старт (локально)

Репозиторий: [github.com/Va11eyard/cornea](https://github.com/Va11eyard/cornea.git)

```bash
git clone https://github.com/Va11eyard/cornea.git
cd cornea
python3 -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Открыть: http://localhost:8001

**Учётная запись администратора по умолчанию:**
- Логин: `admin_cornea`
- Пароль: `mydxQVkwjGU4l-vBi4TyzM` (при каждом старте приложения хеш в БД приводится к значению из кода; смена пароля только вручную в SQLite или правкой хеша в `database.py`)


## Деплой на сервер (VPS, Ubuntu, systemd + Nginx)

Подходит для VPS у [ps.kz](https://ps.kz) и аналогов: на сервере по SSH клонируете репозиторий, поднимаете отдельный порт (если другой проект уже занял `8001` — возьмите, например, `8002` и поправьте `proxy_pass`).

### 1. Клонирование с GitHub

На сервере (под своим пользователем или отдельным каталогом, например `/opt/cornea`):

```bash
sudo mkdir -p /opt/cornea
sudo chown "$USER":"$USER" /opt/cornea
git clone https://github.com/Va11eyard/cornea.git /opt/cornea
```

Дальше обновления — см. ниже «как ProEcta».

### Обновление на сервере proecta (по аналогии с ProEcta)

У Cornea **нет** отдельного фронтенда и `npm run build`: шаблоны и `static/` уже в репозитории, отдаёт всё uvicorn за Nginx.

```bash
ssh proecta
sudo -i   # по желанию, если нужен root для git/systemctl

cd /opt/cornea
git pull origin main

source /opt/cornea/venv/bin/activate
pip install -r requirements.txt

sudo systemctl restart cornea
# nginx трогать только если меняли конфиг сайта:
# sudo nginx -t && sudo systemctl reload nginx
```

Если каталог принадлежит `www-data` и `git pull` без sudo не проходит:

```bash
sudo -u www-data git -C /opt/cornea pull origin main
```

(или один раз выдать себе права на `/opt/cornea` и делать `git pull` под своим пользователем.)

### 2. Виртуальное окружение и зависимости

```bash
cd /opt/cornea
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Файл `cornea.db` создаётся при первом запуске и в `.gitignore` — на сервере он не перезапишется при `git pull`.

### 3. Секретный ключ сессии

В `main.py` замените:

```python
secret_key="cornea-secret-key-change-in-prod-2024"
```

на случайную строку **не короче 40 символов** (до деплоя в прод).

### 4. systemd

Порт **8001** ниже — если занят первым проектом, замените на свободный (и в Nginx тот же порт).

```bash
sudo nano /etc/systemd/system/cornea.service
```

```ini
[Unit]
Description=Cornea Requests App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/cornea
ExecStart=/opt/cornea/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Права на каталог (чтобы `www-data` мог писать `cornea.db` и `app.log`):

```bash
sudo chown -R www-data:www-data /opt/cornea
# при необходимости после git pull снова выдать права на запись в каталог
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cornea
sudo systemctl start cornea
sudo systemctl status cornea
```

### 5. Nginx — два домена на одном сервере (cornea.kz и pro-ecta.kz)

**Да, конфиг Nginx нужно настроить так, чтобы по имени хоста открывался нужный проект.** Браузер при запросе шлёт заголовок `Host: cornea.kz` или `Host: pro-ecta.kz`; Nginx сопоставляет его с директивой `server_name` и отправляет трафик на свой `proxy_pass` (или на статику в `root`).

- **pro-ecta.kz** → ваш существующий ProEcta (бэкенд на своём порту, фронт из `/var/www/proecta-front/...` — как у вас уже настроено).
- **cornea.kz** → отдельный блок `server` с `proxy_pass` на порт uvicorn Cornea (например `8001`).

Оба блока слушают `listen 80` (и при наличии сертификатов — `listen 443 ssl`), но **разные** `server_name` — конфликта нет.

Пример **дополнительного** блока только для Cornea (первый проект не трогайте):

```nginx
server {
    listen 80;
    server_name cornea.kz www.cornea.kz;

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

У ProEcta в другом файле или в том же, но отдельным `server { ... }`, будет что-то вроде `server_name pro-ecta.kz www.pro-ecta.kz;` и свой `proxy_pass` / `root` — **порт бэкенда ProEcta и путь к статике должны отличаться** от Cornea.

После **любого** изменения конфигов:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Обновление кода Cornea (`git pull`, `restart cornea`) **не требует** перезагрузки Nginx, если вы не меняли конфиги. После правки DNS (A-запись на IP сервера) и выпуска сертификата для `cornea.kz` добавьте в этот же `server` блоки `listen 443 ssl` или снова прогоните `certbot`.

**Пока домен cornea.kz в ожидании регистрации:** сайт по имени откроется только после делегирования DNS (A-запись на IP VPS в панели регистратора/ps.kz). До этого можно проверять по `http://IP_СЕРВЕРА:8001` (если firewall открыт) или временно прописать в `/etc/hosts` на своём ПК: `IP_СЕРВЕРА cornea.kz`.

### 6. HTTPS (после того, как домен указывает на сервер)

```bash
sudo certbot --nginx -d cornea.kz -d www.cornea.kz
```

### Альтернатива без Git

```bash
scp -r ./cornea user@SERVER_IP:/opt/cornea
```

(загрузите содержимое репозитория, без `venv/` и без продакшен-`cornea.db`, если не нужен перенос данных).

---

## Структура проекта

```
cornea/   (корень репозитория)
├── main.py
├── database.py
├── phone_validation.py
├── requirements.txt
├── cornea.db                # создаётся локально/на сервере, в git не коммитится
├── routers/
│   ├── auth.py
│   ├── doctor.py
│   └── admin.py
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── doctor/
│   └── admin/
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
