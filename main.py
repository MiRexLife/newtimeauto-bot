import logging
import os
import json
from aiogram import Bot, Dispatcher, types, executor
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
logger.info("Загрузка переменных окружения завершена.")

# Переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")

# Инициализация бота и OpenAI
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)
openai.api_key = OPENAI_API_KEY
logger.info("Бот и OpenAI инициализированы.")

# Подключение к Google Sheets
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT)
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Наличие1")
    logger.info("Успешно подключено к Google Sheets.")
except Exception as e:
    logger.error(f"Ошибка при подключении к Google Sheets: {e}")

# Обработчик команды /start
@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    logger.info(f"Получен запрос /start от {message.from_user.username}")
    await message.reply("Привет! Я помогу подобрать авто. Напиши, что ты ищешь: марку, модель, год, кузов, бюджет и т.д.")

# Функция для парсинга критериев из запроса
def parse_criteria(text):
    criteria = {}
    words = text.lower().split()

    for word in words:
        if word.isdigit():
            if int(word) > 1990:
                criteria["Год"] = int(word)
            else:
                criteria["Цена"] = int(word)
        elif word in ["седан", "внедорожник", "хэтчбек", "купе"]:
            criteria["Кузов"] = word
        else:
            criteria["Марка"] = word.capitalize()

    return criteria

# Функция для поиска совпадений с автомобилем
def match_car(car, criteria):
    for key, value in criteria.items():
        if key not in car:
            continue
        car_value = str(car[key]).lower()
        if key == "Цена":
            try:
                if int(car[key]) > int(value):
                    return False
            except:
                return False
        elif key == "Год":
            try:
                if int(car[key]) < int(value):
                    return False
            except:
                return False
        else:
            if value.lower() not in car_value:
                return False
    return True

# Функция для общения с GPT
async def ask_gpt(question):
    try:
        logger.info(f"Запрос к GPT: {question}")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Используем правильную модель
            messages=[
                {"role": "system", "content": "Ты автоэксперт, помогай людям с вопросами про покупку авто."},
                {"role": "user", "content": question}
            ]
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        logger.error(f"Ошибка GPT: {e}")
        return "Произошла ошибка при обращении к ИИ."

# Основной обработчик сообщений
@dp.message_handler()
async def handle_query(message: types.Message):
    logger.info(f"Получен запрос от {message.from_user.username}: {message.text}")
    query = message.text
    criteria = parse_criteria(query)
    cars = sheet.get_all_records()
    matches = []

    for car in cars:
        if match_car(car, criteria):
            matches.append(car)
        if len(matches) >= 3:
            break

    if matches:
        for car in matches:
            try:
                text = f"{car.get('Марка', '—')} {car.get('Модель', '')} {car.get('Год', '')}\nЦена: {car.get('Цена', '—')}₽\nЦвет: {car.get('Цвет', '—')}"
                kb = types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("Забронировать", url="https://t.me/NewTimeAuto_bot")
                )
                logger.info(f"Ответ для пользователя {message.from_user.username}: {text}")
                await message.reply(text, reply_markup=kb)
            except Exception as e:
                logger.error(f"Ошибка при обработке машины: {car}\n{e}")
                continue
    else:
        gpt_answer = await ask_gpt(query)
        logger.info(f"Ответ от GPT для запроса {query}: {gpt_answer}")
        await message.reply(f"🤖 {gpt_answer}")

# Запуск бота
if __name__ == "__main__":
    logger.info("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)
