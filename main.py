import os
import json
import logging
import urllib.parse
import re
from dotenv import load_dotenv
import gspread
from openai import OpenAI
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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

# Простая память для ИИ (на сессию)
chat_histories = {}

# Функция поиска авто по ключевым словам
def search_cars_by_keywords(query):
    if not sheet:
        return []

    try:
        stop_words = {"ищу", "хочу", "нужен", "нужна", "нужно", "подобрать"}
        query_words = re.findall(r'\w+', query.lower())
        keywords = [word for word in query_words if word not in stop_words]

        values = sheet.get_all_values()
        headers = values[0]
        rows = values[1:]

        matches = []

        for row in rows:
            row_dict = dict(zip(headers, row))
            row_text = " ".join(value.lower() for value in row_dict.values())
            if all(word in row_text for word in keywords):
                matches.append(row_dict)
                if len(matches) >= 3:
                    break

        return matches
    except Exception as e:
        logger.error(f"Ошибка при поиске в таблице: {e}")
        return []

# Проверка на необходимость перевода к менеджеру
def needs_manager(reply):
    phrases = ["не знаю", "не определился", "менеджер", "оператор", "человек", "отвали", "помоги"]
    return any(phrase in reply.lower() for phrase in phrases)

# Обработка команды /start
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer("Привет! Напиши, какую машину ты ищешь (например: 'BMW X1')")

# Обработка обычных сообщений
@dp.message_handler()
async def handle_query(message: types.Message):
    user_id = message.from_user.id
    user_query = message.text.strip()
    logger.info(f"Получен запрос от {message.from_user.username}: {user_query}")

    # Поиск в таблице
    matches = search_cars_by_keywords(user_query)
    if matches:
        for car in matches:
            car_info = "\n".join([f"{k}: {v}" for k, v in car.items()])

            car_id = car.get("ID")  # ID теперь точно в формате "001", "002", и т.д.
            query_encoded = urllib.parse.quote(f"Здравствуйте! Интересует: {user_query}, ID: {car_id}")
            site_url = f"https://mirexlife.github.io/newtimeauto-site/car.html?id={car_id}"

            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("📩 Подробнее", url=site_url)
            )

            await message.answer(car_info, reply_markup=keyboard)
        return

    # Если не нашли — пробуем GPT с историей
    try:
        history = chat_histories.get(user_id, [])
        history.append({"role": "user", "content": user_query})

        messages = [
            {"role": "system", "content": "Ты автоассистент. Отвечай кратко и по запросу. Завершай ответ наводящим вопросом. Если клиент не может определиться, отправь к менеджеру @NewTimeAuto_sales."}
        ] + history

        chat_completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )

        reply = chat_completion.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": reply})
        chat_histories[user_id] = history[-10:]  # Храним последние 10 сообщений

        # Отправляем ответ от ИИ
        await message.answer(reply)

        if needs_manager(reply):
            full_history = "\n".join([m["content"] for m in history if m["role"] == "user"])
            query_encoded = urllib.parse.quote(f"Здравствуйте, хочу поговорить о подборе авто.\n\nИстория:\n{full_history}")
            manager_url = f"https://t.me/newtimeauto_sales?text={query_encoded}"

            # Убедитесь, что передаете text в message.answer() здесь
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("Связаться с менеджером", url=manager_url)
            )
            await message.answer("Если вам нужно помочь, свяжитесь с менеджером:", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка GPT: {e}")
        await message.answer("ИИ пока не работает, но вы можете уточнить запрос или задать другой.")

# Запуск бота
if __name__ == "__main__":
    logger.info("Бот запущен.")
    executor.start_polling(dp, skip_updates=True)
