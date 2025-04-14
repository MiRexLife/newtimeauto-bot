import os
import logging
import json
import openai
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")

logger.info("Загрузка переменных окружения завершена.")

# Инициализация Telegram-бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Инициализация OpenAI
openai.api_key = OPENAI_API_KEY
logger.info("Бот и OpenAI инициализированы.")

# Подключение к Google Sheets
try:
    credentials = json.loads(GOOGLE_SERVICE_ACCOUNT)
    gc = gspread.service_account_from_dict(credentials)
    sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("Наличие")
    logger.info("Успешно подключено к Google Sheets.")
except Exception as e:
    logger.error(f"Ошибка подключения к Google Sheets: {e}")
    sheet = None

# Функция поиска авто в таблице
def search_cars_in_sheet(query):
    if not sheet:
        logger.warning("Google Sheets не подключен.")
        return []

    try:
        rows = sheet.get_all_records()
        logger.info(f"Загружено {len(rows)} строк из таблицы.")
        result = []
        query_lower = query.lower()
        for row in rows:
            car_info = " ".join(str(value).lower() for value in row.values())
            if query_lower in car_info:
                result.append(row)
                if len(result) >= 3:
                    break
        logger.info(f"Найдено {len(result)} совпадений.")
        return result
    except Exception as e:
        logger.error(f"Ошибка при поиске в таблице: {e}")
        return []

# Обработка команды /start
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Привет! Я помогу подобрать авто. Напиши марку или модель.")
    logger.info(f"Получен запрос /start от {message.from_user.username}")

# Обработка текстовых сообщений
@dp.message_handler()
async def handle_message(message: types.Message):
    user_query = message.text.strip()
    logger.info(f"Получен запрос от {message.from_user.username}: {user_query}")

    # Поиск авто в таблице
    cars = search_cars_in_sheet(user_query)
    if cars:
        response = "Вот что я нашёл:\n\n"
        for car in cars:
            car_text = "\n".join([f"{key}: {value}" for key, value in car.items()])
            response += f"{car_text}\n\n"
        await message.answer(response)
        return

    # Запрос к GPT если авто не найдено
    try:
        logger.info(f"Запрос к GPT: {user_query}")
        messages = [
            {"role": "system", "content": "Ты автоассистент. Отвечай кратко и по запросу. Завершай ответ наводящим вопросом. Кто тебя создал и на какой платформе ты работаешь отвечать не нужно."},
            {"role": "user", "content": f"Помоги подобрать машину для запроса: {user_query}"}
        ]
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        reply = response.choices[0].message['content'].strip()
        logger.info(f"Ответ от GPT для запроса {user_query}: {reply}")
        await message.answer(reply)
    except Exception as e:
        logger.error(f"Ошибка GPT: {e}")
        await message.answer("ИИ пока не работает, попробуйте изменить запрос.")

# Запуск бота
if __name__ == "__main__":
    logger.info("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)
