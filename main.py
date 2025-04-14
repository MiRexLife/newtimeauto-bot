import logging
import os
import re
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

def extract_filters(text):
    filters = {
        "min_price": 0,
        "max_price": float('inf'),
        "min_year": 0,
        "max_year": 9999,
        "min_mileage": 0,
        "max_mileage": float('inf'),
        "gearbox": None,
        "engine": None,
        "keywords": []
    }

    # Цена
    price_match = re.findall(r"\d[\d\s]*[kкКК]|\d[\d\s]*[мМ]н|\d[\d\s]*000", text)
    if price_match:
        numbers = []
        for p in price_match:
            num = int(re.sub(r"\D", "", p))
            if "м" in p.lower():
                num *= 1_000_000
            elif "к" in p.lower():
                num *= 1_000
            numbers.append(num)
        if len(numbers) == 1:
            filters["max_price"] = numbers[0]
        elif len(numbers) >= 2:
            filters["min_price"], filters["max_price"] = sorted(numbers[:2])

    # Год
    year_match = re.findall(r"от\s*(\d{4})|до\s*(\d{4})|(\d{4})\s*[-–]\s*(\d{4})", text)
    for match in year_match:
        if match[0]:
            filters["min_year"] = int(match[0])
        if match[1]:
            filters["max_year"] = int(match[1])
        if match[2] and match[3]:
            filters["min_year"] = int(match[2])
            filters["max_year"] = int(match[3])

    # Пробег
    mileage_match = re.findall(r"пробег\s*(\d+)[–-](\d+)|до\s*(\d+)\s*тыс", text)
    for m in mileage_match:
        if m[0] and m[1]:
            filters["min_mileage"] = int(m[0]) * 1000
            filters["max_mileage"] = int(m[1]) * 1000
        elif m[2]:
            filters["max_mileage"] = int(m[2]) * 1000

    # Коробка
    if "автомат" in text:
        filters["gearbox"] = "автомат"
    elif "механика" in text:
        filters["gearbox"] = "механика"
    elif "вариатор" in text:
        filters["gearbox"] = "вариатор"

    # Двигатель
    if "бензин" in text:
        filters["engine"] = "бензин"
    elif "дизель" in text:
        filters["engine"] = "дизель"
    elif "гибрид" in text:
        filters["engine"] = "гибрид"
    elif "электро" in text or "электромобиль" in text:
        filters["engine"] = "электро"

    # Ключевые слова
    filters["keywords"] = [w.strip() for w in re.findall(r"[а-яa-zA-ZёЁ0-9]+", text) if len(w) > 2]

    return filters

@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Я помогу подобрать авто. Напиши, что ты ищешь: бюджет, год, пробег, марка, кузов и т.д.")

@dp.message_handler()
async def handle_query(message: types.Message):
    query = message.text.lower()
    filters = extract_filters(query)
    cars = sheet.get_all_records()

    matches = []
    for car in cars:
        try:
            price = int(re.sub(r"\D", "", str(car["Цена"])))
            year = int(car["Год"])
            mileage = int(re.sub(r"\D", "", str(car.get("Пробег", "0"))))
            gearbox = car.get("Коробка", "").lower()
            engine = car.get("Двигатель", "").lower()
        except:
            continue

        if not (filters["min_price"] <= price <= filters["max_price"]):
            continue
        if not (filters["min_year"] <= year <= filters["max_year"]):
            continue
        if not (filters["min_mileage"] <= mileage <= filters["max_mileage"]):
            continue
        if filters["gearbox"] and filters["gearbox"] not in gearbox:
            continue
        if filters["engine"] and filters["engine"] not in engine:
            continue

        car_text = f"{car['Марка']} {car['Модель']} {car['Кузов']}".lower()
        if all(kw in car_text for kw in filters["keywords"]):
            matches.append(car)

        if len(matches) >= 3:
            break

    if matches:
        for car in matches:
            text = f"""\
{car['Марка']} {car['Модель']} {car['Год']}
Цена: {car['Цена']}₽
Пробег: {car.get('Пробег', '—')}
Цвет: {car['Цвет']}
Двигатель: {car.get('Двигатель', '—')}
Коробка: {car.get('Коробка', '—')}"""
            kb = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Забронировать", url="https://t.me/NewTimeAuto_bot")
            )
            await message.reply(text, reply_markup=kb)
    else:
        await message.reply("Не нашёл подходящих авто. Попробуй изменить запрос.")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)