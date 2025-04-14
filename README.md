# NewTimeAuto Telegram Bot

Бот для подбора автомобилей из Google Таблицы.

## Установка

1. Добавьте файл `google_service.json` в корень проекта (скачан с Google Cloud Console)
2. Создайте `.env` файл на основе `.env.example` и добавьте:
   - `TELEGRAM_TOKEN` — токен от @NewTimeAuto_bot
   - `SPREADSHEET_ID` — ID вашей Google Таблицы

## Запуск на Railway

1. Форкните этот репозиторий
2. Подключите Railway к GitHub
3. Railway автоматически подтянет `Procfile` и зависимости