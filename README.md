# WikiBot — Telegram Wikipedia Bot

Telegram-бот для создания иерархических баз знаний: **Папки → Группы → Статьи**.

## Возможности

- 📁 Иерархия: Папки → Группы → Статьи с неограниченной вложенностью
- 📝 Редактор статей: текст с HTML-форматированием + фото + ссылки
- 🔒 Три режима доступа: Приватный / По ссылке / Публичный
- ❤️ Лайки и 💬 Комментарии
- 👥 Соавторы (редакторы) для папок, групп и статей
- 🌍 Публичная лента (Новое / Залайканное)
- 🔍 Поиск по публичным статьям и папкам
- 👤 Профиль пользователя

## Быстрый старт

### 1. Получить токен

Создайте бота через [@BotFather](https://t.me/BotFather), получите токен.

### 2. Переменные окружения

```bash
export TELEGRAM_TOKEN=ваш_токен
# Опционально:
export DB_PATH=wikibot/wikibot.db       # путь к SQLite
export KEEP_ALIVE=1                     # включить веб-сервер для Replit
```

### 3. Установка зависимостей

```bash
pip install -r wikibot/requirements.txt
```

### 4. Запуск

```bash
python wikibot/main.py
```

## Запуск на Railway / Heroku / VPS

1. Установить переменную `TELEGRAM_TOKEN`
2. `pip install -r wikibot/requirements.txt`
3. `python wikibot/main.py`

## Запуск на Replit

1. Добавить секрет `TELEGRAM_TOKEN` в Secrets
2. Нажать Run — бот запустится автоматически

## Запуск через Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY wikibot/requirements.txt .
RUN pip install -r requirements.txt
COPY wikibot/ .
CMD ["python", "main.py"]
```

## База данных

- **По умолчанию**: SQLite (`wikibot/wikibot.db`)
- **PostgreSQL**: задайте `DB_PATH` или измените `database.py` для поддержки pg

## Структура проекта

```
wikibot/
├── main.py          # Точка входа, настройка бота
├── database.py      # Все операции с БД
├── keyboards.py     # Все inline-клавиатуры
├── utils.py         # Вспомогательные функции
├── requirements.txt
├── handlers/
│   ├── common.py    # /start, главное меню
│   ├── folders.py   # Папки
│   ├── groups.py    # Группы
│   ├── articles.py  # Статьи, лайки, комментарии, поиск
│   ├── editors.py   # Управление редакторами
│   └── public.py    # Публичная лента, профиль
```
