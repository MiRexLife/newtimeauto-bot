import logging
import os
import json
from aiogram import Bot, Dispatcher, types, executor
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

# Переменные окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_SERVICE_ACCOUNT = os.getenv("GOOGLE_SERVICE_ACCOUNT")

# Инициализация
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)
openai.api_key = OPENAI_API_KEY

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT)
credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Наличие1")

@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Я помогу подобрать авто. Напиши, что ты ищешь: марку, модель, год, кузов, бюджет и т.д.")

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

async def ask_gpt(question):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты автоэксперт, помогай людям с вопросами про покупку авто."},
                {"role": "user", "content": question}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Ошибка GPT: {e}")
        return "Произошла ошибка при обращении к ИИ."

@dp.message_handler()
async def handle_query(message: types.Message):
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
 print(car)  # 👈 Добавь вот эту строку для отладки
            try:
    text = f"{car.get('Марка', '—')} {car.get('Модель', '')} {car.get('Год', '')}\nЦена: {car.get('Цена', '—')}₽\nЦвет: {car.get('Цвет', '—')}"
except Exception as e:
    logging.error(f"Ошибка при форматировании авто: {e}")
    continue
            kb = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Забронировать", url="https://t.me/NewTimeAuto_bot")
            )
            await message.reply(text, reply_markup=kb)
    else:
        gpt_answer = await ask_gpt(query)
        await message.reply(f"🤖 {gpt_answer}")

if __name__ == "__main__":
    print("Бот запущен...")
    executor.start_polling(dp, skip_updates=True)
