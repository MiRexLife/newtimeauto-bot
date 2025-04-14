import os
import json
import logging
from dotenv import load_dotenv
import gspread
from openai import OpenAI
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")

# Инициализация OpenAI клиента
client = OpenAI(api_key=OPENAI_API_KEY)

# Инициализация Telegram-бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Подключение к Google Sheets
try:
    credentials = json.loads(GOOGLE_SERVICE_ACCOUNT)
    gc = gspread.service_account_from_dict(credentials)
    sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("Наличие")
    logger.info("Успешно подключено к Google Sheets.")
except Exception as e:
    logger.error(f"Ошибка подключения к Google Sheets: {e}")
    sheet = None

# Функция поиска авто по ключевым словам
def search_cars_by_keywords(query):
    if not sheet:
        return []

    try:
        keywords = query.lower().split()
        rows = sheet.get_all_records()
        matches = []

        for row in rows:
            row_text = " ".join(str(value).lower() for value in row.values())
            if all(word in row_text for word in keywords):
                matches.append(row)
                if len(matches) >= 3:
                    break

        return matches
    except Exception as e:
        logger.error(f"Ошибка при поиске в таблице: {e}")
        return []

# Обработка команды /start
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer("Привет! Напиши, какую машину ты ищешь (например: 'BMW X1 дизель 2020')")

# Обработка обычных сообщений
@dp.message_handler()
async def handle_query(message: types.Message):
    user_query = message.text.strip()
    logger.info(f"Запрос пользователя: {user_query}")

    # Поиск в таблице
    matches = search_cars_by_keywords(user_query)
    if matches:
        response = "Вот что я нашёл:\n\n"
        for car in matches:
            car_info = "\n".join([f"{k}: {v}" for k, v in car.items()])
            response += f"{car_info}\n\n"
        await message.answer(response)
        return

    # Если не нашли — пробуем GPT
    try:
        logger.info("Запрос к GPT...")
        chat_completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты автоассистент, помоги подобрать машину."},
                {"role": "user", "content": user_query}
            ],
            temperature=0.7,
            max_tokens=300
        )
        reply = chat_completion.choices[0].message.content.strip()
        await message.answer(reply)
    except Exception as e:
        logger.error(f"Ошибка GPT: {e}")
        await message.answer("ИИ пока не работает, но вы можете уточнить запрос или задать другой!")

# Запуск бота
if __name__ == "__main__":
    logger.info("Бот запущен.")
    executor.start_polling(dp, skip_updates=True)
