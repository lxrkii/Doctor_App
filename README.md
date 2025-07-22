# Инструкция по запуску на сервере (timeweb.cloud)

## Установка зависимостей
```
pip install -r requirements.txt
```

## Запуск FastAPI (админ-панель)
```
uvicorn admin_panel.main:app --host 0.0.0.0 --port 8000
```

Или, если используется Procfile, сервис запустится автоматически.

## Запуск Telegram-бота
```
python bot/main.py
```

---

# Локальный запуск

1. Перейти в папку app:
```
cd app
```
2. Активировать виртуальное окружение (если есть):
```
source ../.venv/bin/activate
```
3. Установить зависимости:
```
pip install -r requirements.txt
```
4. Запустить FastAPI:
```
uvicorn admin_panel.main:app --reload --host 0.0.0.0 --port 8000
```
5. Запустить Telegram-бота:
```
python bot/main.py
```
