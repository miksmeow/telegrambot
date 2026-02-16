import io, asyncio, threading
from flask import Flask, request, send_file
from telegraph import Telegraph
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8594559077:AAFoKX-w7hpYDXkbHc3kTEcesO4vb5fW-nw"
YOUR_DOMAIN = "https://zoophagous-leilah-telepuziki-8e2398a3.koyeb.app" 
MY_ID = 7462192673  

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
tg = Telegraph()
tg.create_account(short_name='News-Bot')

# Нужен глобальный loop для связи Flask и Бота
loop = asyncio.new_event_loop()

@app.route('/')
def index():
    return "System Online", 200

@app.route('/log/<log_id>.png')
def logger(log_id):
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0]
    else:
        ip = request.remote_addr
    ua = request.headers.get('User-Agent')
    
    # Отправка сообщения из Flask в Telegram
    asyncio.run_coroutine_threadsafe(
        bot.send_message(MY_ID, f"🔔 **ПЕРЕХОД!**\n\n📍 IP: `{ip}`\n📱 UA: `{ua}`\n🔗 ID: `{log_id}`"),
        loop
    )

    pixel = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    return send_file(io.BytesIO(pixel), mimetype='image/png')

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ Бот активен! Пришли: `Заголовок | Текст` ")

@dp.message()
async def create_link(message: types.Message):
    if "|" not in message.text: return
    title, text = message.text.split("|", 1)
    content = [{"tag": "p", "children": [text.strip()]},
               {"tag": "img", "attrs": {"src": f"{YOUR_DOMAIN}/log/{message.message_id}.png"}}]
    response = tg.create_page(title=title.strip(), content=content)
    await message.answer(f"🔗 Готово: {response['url']}")

# Функция для запуска бота в отдельном потоке
def start_bot():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(dp.start_polling(bot))

# Запускаем бота сразу при импорте модуля
threading.Thread(target=start_bot, daemon=True).start()

# Для Gunicorn основной объект - app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
