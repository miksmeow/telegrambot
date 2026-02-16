import io
import asyncio
from flask import Flask, request, send_file
from telegraph import Telegraph
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from threading import Thread

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8594559077:AAFoKX-w7hpYDXkbHc3kTEcesO4vb5fW-nw"
# Убедись, что этот домен совпадает с твоим текущим приложением на Koyeb
YOUR_DOMAIN = "https://zoophagous-leilah-telepuziki-8e2398a3.koyeb.app" 
MY_ID = 7462192673  

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
tg = Telegraph()
tg.create_account(short_name='News-Bot')

# --- ЧАСТЬ 1: ЛОГГЕР (FLASK) ---

@app.route('/')
def index():
    # Заглушка, чтобы Koyeb не видел 404 и не ругался
    return "System Online", 200

@app.route('/log/<log_id>.png')
def logger(log_id):
    # На хостингах типа Koyeb реальный IP скрыт за прокси. Достаем его правильно:
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0]
    else:
        ip = request.remote_addr
        
    ua = request.headers.get('User-Agent')
    
    # Отправляем уведомление в Телеграм
    asyncio.run_coroutine_threadsafe(
        bot.send_message(MY_ID, f"🔔 **НОВЫЙ ПЕРЕХОД!**\n\n📍 IP: `{ip}`\n📱 Device: `{ua}`\n🔗 ID статьи: `{log_id}`"),
        loop
    )

    # Отдаем прозрачный пиксель 1x1
    pixel = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    return send_file(io.BytesIO(pixel), mimetype='image/png')

# --- ЧАСТЬ 2: БОТ (AIOGRAM) ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("👋 Привет! Я создам статью в Telegraph с IP-логгером.\n\n"
                         "Пришли мне заголовок и текст через вертикальную черту.\n"
                         "Пример: `Свежие новости | Тут очень интересный текст` ")

@dp.message()
async def create_link(message: types.Message):
    if "|" not in message.text:
        return await message.answer("❌ Ошибка! Используй формат: `Заголовок | Текст` ")
    
    title, text = message.text.split("|", 1)
    # Используем время или ID сообщения для уникальности ссылки на картинку
    log_id = message.message_id 
    
    # Формируем контент для Telegraph
    content = [
        {"tag": "p", "children": [text.strip()]},
        # Вставляем невидимый логгер
        {"tag": "img", "attrs": {"src": f"{YOUR_DOMAIN}/log/{log_id}.png"}}
    ]
    
    try:
        response = tg.create_page(
            title=title.strip(), 
            content=content,
            author_name="Telegraph News"
        )
        await message.answer(f"✅ **Статья готова!**\n\nСсылка:\n{response['url']}")
    except Exception as e:
        await message.answer(f"❌ Ошибка API Telegraph: {e}")

# --- ИНИЦИАЛИЗАЦИЯ И ЗАПУСК ---

def run_flask():
    # Koyeb по умолчанию использует порт 8000
    app.run(host='0.0.0.0', port=8000)

if __name__ == '__main__':
    # Создаем событие цикла для асинхронности
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Запускаем веб-сервер в отдельном потоке
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print(">>> Логгер-сервер запущен на порту 8000")
    print(">>> Бот начинает опрос...")
    
    try:
        loop.run_until_complete(dp.start_polling(bot))
    except KeyboardInterrupt:
        print("Бот остановлен.")
