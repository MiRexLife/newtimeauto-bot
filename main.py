import os
import logging
import json
import openai
import gspread
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv
import re

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

# Функция поиска авто в таблице с учетом ключевых слов
def search_cars_in_sheet(query):
    if not sheet:
        logger.warning("Google Sheets не подключен.")
        return []

    try:
        # Загружаем все строки из таблицы
        rows = sheet.get_all_records()
        logger.info(f"Загружено {len(rows)} строк из таблицы.")
        result = []

        # Преобразуем запрос в список ключевых слов
        query_lower = query.lower()
        keywords = re.findall(r'\b\w+\b', query_lower)  # Извлекаем все слова из запроса

        for row in rows:
            # Преобразуем информацию о машине в строку
            car_info = " ".join(str(value).lower() for value in row.values())

            # Проверяем, содержатся ли все ключевые слова в информации о машине
            if all(keyword in car_info for keyword in keywords):
                result.append(row)
                if len(result) >= 3:  # Ограничиваем количество результатов
                    break
        
        logger.info(f"Найдено {len(result)} совпадений.")
        return result
    except Exception as e:
        logger.error(f"Ошибка при поиске в таблице: {e}")
        return []

# Функция обработки запроса через GPT
def get_gpt_response(query):
    try:
        logger.info(f"Запрос к GPT: {query}")
        response = openai.Completion.create(
            model="gpt-3.5-turbo",
            prompt=f"Ты автоассистент. Не пиши кто тебя создал, на какой платформе ты работаешь, Отвечай коротко и по запросу. Помоги подобрать машину для запроса: {query}",
            max_tokens=300,
            temperature=0.7
        )
        reply = response.choices[0].text.strip()
        logger.info(f"Ответ от GPT для запроса {query}: {reply}")
        return reply
    except Exception as e:
        logger.error(f"Ошибка GPT: {e}")
        return "Извините, возникла ошибка при обработке вашего запроса через ИИ."

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

    # Поиск авто в таблице Google
    cars = search_cars_in_sheet(user_query)
    if cars:
        response = "Вот что я нашёл:\n\n"
        for car in cars:
            car_text = "\n".join([f"{key}: {value}" for key, value in car.items()])
            response += f"{car_text}\n\n"
        await message.answer(response)
    else:
        # Если авто не найдено в таблице, используем GPT для ответа
        gpt_response = get_gpt_response(user_query)
        await message.answer(gpt_response)

# Запуск бота
if __name__ == "__main__":
    logger.info("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)