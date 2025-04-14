import logging
import os
from aiogram import Bot, Dispatcher, types, executor
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Настройка Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("google_service.json", scope)
client = gspread.authorize(credentials)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet("Наличие")

@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Я помогу подобрать авто. Напиши, что ты ищешь: бюджет, год, марка, кузов и т.д.")

@dp.message_handler()
async def handle_query(message: types.Message):
    query = message.text.lower()
    cars = sheet.get_all_records()

    matches = []
    for car in cars:
        if any(q in str(car).lower() for q in query.split()):
            matches.append(car)
        if len(matches) >= 3:
            break

    if matches:
        for car in matches:
            text = f"{car['Марка']} {car['Модель']} {car['Год']}
Цена: {car['Цена']}₽
Цвет: {car['Цвет']}"
            kb = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Забронировать", url="https://t.me/NewTimeAuto_bot")
            )
            await message.reply(text, reply_markup=kb)
    else:
        await message.reply("Не нашёл подходящих авто. Попробуй изменить запрос.")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)