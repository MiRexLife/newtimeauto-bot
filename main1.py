import logging
import os
import json
from aiogram import Bot, Dispatcher, types, executor
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import openai

# Загрузка переменных окружения из .env
load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Инициализация бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Настройка Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT)
credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Наличие")

# Инициализация OpenAI
openai.api_key = OPENAI_API_KEY

# Функция для получения ответа от GPT
def get_gpt_response(user_input):
    response = openai.Completion.create(
        model="gpt-4",  # Используем GPT-4
        prompt=f"Ответь на вопрос по автомобильной тематике: {user_input}",
        max_tokens=150
    )
    return response.choices[0].text.strip()

# Обработчик команды /start
@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Я помогу подобрать авто. Напиши, что ты ищешь: марку, кузов, год, бюджет и т.д.")

# Функция для парсинга запроса пользователя
def parse_criteria(text):
    criteria = {}
    words = text.lower().split()

    for word in words:
        if word.isdigit():
            if int(word) > 1990:
                criteria["Год"] = int(word)
            else:
                criteria["Цена"] = int(word)
        elif word in ["седан", "внедорожник", "хэтчбек", "купе", "лифтбек", "спорткар", "электро"]:
            criteria["Кузов"] = word
        else:
            criteria["Марка"] = word.capitalize()

    return criteria

# Функция для сопоставления автомобиля с критериями
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

# Обработчик всех сообщений
@dp.message_handler()
async def handle_query(message: types.Message):
    query = message.text
    # Проверяем, является ли запрос вопросом по автомобилям
    if "?" in query:
        gpt_response = get_gpt_response(query)
        await message.reply(gpt_response)
    else:
        # Парсим запрос по критериям
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
                text = f"{car['Марка']} {car['Модель']} {car['Год']}\nЦена: {car['Цена']}₽\nЦвет: {car['Цвет']}"
                kb = types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("Забронировать", url="https://t.me/NewTimeAuto_bot")
                )
                await message.reply(text, reply_markup=kb)
        else:
            await message.reply("Не нашёл подходящих авто. Попробуй изменить запрос.")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
