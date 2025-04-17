# ... (всё как раньше: импорты, переменные, инициализация Telegram, Google Sheets и OpenAI) ...

# Функция: получить авто по ID
def get_car_by_id(car_id):
    try:
        values = sheet.get_all_values()
        headers = values[0]
        rows = values[1:]

        for row in rows:
            row_dict = dict(zip(headers, row))
            if row_dict.get("ID") == car_id:
                return row_dict
        return None
    except Exception as e:
        logger.error(f"Ошибка при поиске авто по ID: {e}")
        return None

# Обработка команды /start
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    # Проверяем, пришло ли startapp=id_001
    if message.get_args().startswith("id_"):
        car_id = message.get_args().replace("id_", "")
        car = get_car_by_id(car_id)
        if car:
            car_info = "\n".join([f"{k}: {v}" for k, v in car.items()])
            site_url = f"https://mirexlife.github.io/newtimeauto-site/car.html?id={car_id}"
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("📩 Подробнее", url=site_url)
            )
            await message.answer(f"Информация по выбранному авто:\n\n{car_info}", reply_markup=keyboard)
        else:
            await message.answer("Автомобиль с таким ID не найден 😕")
    else:
        await message.answer("Привет! Напиши, какую машину ты ищешь (например: 'BMW X1')")

# Обработка команды /help
@dp.message_handler(commands=["help"])
async def cmd_help(message: types.Message):
    await message.answer(
        "👋 Этот ассистент поможет подобрать автомобиль из наличия.\n"
        "Просто напиши, какую машину ищешь, например:\n"
        "`BMW X1 бензин`\n\n"
        "Если не знаешь точно — ассистент задаст уточняющие вопросы.\n"
        "Для связи с менеджером будет кнопка.\n\n",
        parse_mode="Markdown"
    )

# Обработка обычных сообщений (как было)
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
            car_id = car.get("ID")
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
            {"role": "system", "content": "Ты автоассистент. Отвечай кратко и по запросу. Завершай ответ наводящим вопросом. Если клиент не может определиться, отправь к менеджеру прямо здесь в telegram."}
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

        await message.answer(reply)

        if needs_manager(reply):
            full_history = "\n".join([m["content"] for m in history if m["role"] == "user"])
            query_encoded = urllib.parse.quote(f"Здравствуйте, хочу поговорить о подборе авто.\n\nИстория:\n{full_history}")
            manager_url = f"https://t.me/newtimeauto_sales?text={query_encoded}"

            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("Связаться с менеджером", url=manager_url)
            )
            await message.answer(reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Ошибка GPT: {e}")
        await message.answer("ИИ пока не работает, но вы можете уточнить запрос или задать другой.")

# Запуск бота
if __name__ == "__main__":
    logger.info("Бот запущен.")
    executor.start_polling(dp, skip_updates=True)
