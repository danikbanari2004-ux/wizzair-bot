import os
import telebot
import threading
import time
import sqlite3
import requests
from telebot import types
from flask import Flask

# Токен берем из переменных окружения Render
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Сбрасываем старый webhook
try:
    bot.remove_webhook()
except Exception as e:
    print(f"Ошибка при удалении webhook: {e}")

# ==================== БАЗА ДАННЫХ (SQLite) ====================
DB_FILE = "database.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            dep_code TEXT,
            arr_code TEXT,
            dates TEXT,
            last_price REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def add_subscription(chat_id, dep, arr, dates):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM subscriptions WHERE chat_id = ? AND dep_code = ? AND arr_code = ?', (chat_id, dep, arr))
    existing = cursor.fetchone()
    if existing:
        cursor.execute('UPDATE subscriptions SET dates = ? WHERE id = ?', (dates, existing[0]))
    else:
        cursor.execute('INSERT INTO subscriptions (chat_id, dep_code, arr_code, dates, last_price) VALUES (?, ?, ?, ?, ?)', 
                       (chat_id, dep, arr, dates, None))
    conn.commit()
    conn.close()

def get_all_subscriptions():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, chat_id, dep_code, arr_code, dates, last_price FROM subscriptions')
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_subscription_price(sub_id, new_price):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE subscriptions SET last_price = ? WHERE id = ?', (new_price, sub_id))
    conn.commit()
    conn.close()

def delete_user_subscriptions(chat_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM subscriptions WHERE chat_id = ?', (chat_id,))
    conn.commit()
    conn.close()

# ==================== ДИНАМИЧЕСКИЙ ПОИСК АЭРОПОРТОВ ЧЕРЕЗ API ====================
def search_airport_api(query):
    """
    Запрашивает глобальную базу агрегатора авиабилетов.
    Возвращает (code, name) если аэропорт найден, либо None.
    """
    try:
        url = f"https://autocomplete.travelpayouts.com/places2?term={query}&locale=ru&types[]=airport&types[]=city"
        res = requests.get(url, timeout=5).json()
        if res and len(res) > 0:
            item = res[0]
            code = item.get("code")
            name = item.get("name") or item.get("city_name")
            return code, name
    except Exception as e:
        print(f"Ошибка обращения к API автозаполнения: {e}")
    return None, None

user_states = {}

# ==================== HANDLERS ====================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    user_states[chat_id] = {'step': 'FROM'}
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Кишинэу (RMO)", "Яссы (IAS)", "Бухарест (OTP)")
    
    bot.send_message(
        chat_id, 
        "✈️ **Wizz Air Price Tracker Bot**\n\n"
        "Я умею находить любые города мира и отслеживать для тебя минимальные цены!\n\n"
        "**Шаг 1 из 3:** Откуда вылетаем? Выбери из быстрых кнопок или напиши название города:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['my_subs'])
def my_subs_cmd(message):
    chat_id = message.chat.id
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT dep_code, arr_code, dates, last_price FROM subscriptions WHERE chat_id = ?', (chat_id,))
    subs = cursor.fetchall()
    conn.close()
    
    if not subs:
        bot.send_message(chat_id, "📭 У тебя пока нет активных подписок. Нажми /start, чтобы добавить.")
        return
        
    text = "📋 **Твои активные отслеживания:**\n\n"
    for s in subs:
        dep, arr, dates, price = s
        p_str = f"{price} EUR" if price else "запрос информации..."
        text += f"✈️ **{dep} ➔ {arr}**\n📅 Даты: `{dates}`\n💰 Текущая миним. цена: `{p_str}`\n\n"
    
    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(commands=['cancel'])
def cancel_cmd(message):
    chat_id = message.chat.id
    delete_user_subscriptions(chat_id)
    bot.send_message(chat_id, "🗑 Все твои подписки успешно удалены.")

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'FROM')
def get_from_city(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    # Ищем код через API агрегатора
    code, name = search_airport_api(text)
    
    if not code:
        bot.send_message(
            chat_id,
            "❌ **Город не найден.** Проверь написание и введи название города еще раз (например: *Кишинев*, *Яссы*, *Бухарест*):",
            parse_mode="Markdown"
        )
        return
        
    user_states[chat_id]['from'] = code
    user_states[chat_id]['step'] = 'TO'
    
    bot.send_message(
        chat_id,
        f"✅ Отправление: **{name} ({code})**\n\n"
        "**Шаг 2 из 3:** Куда летим? Напиши город назначения (например: *Скиатос*, *Рим*, *Барселона*, *Аликанте*):",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'TO')
def get_to_city(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    code, name = search_airport_api(text)
    
    if not code:
        bot.send_message(
            chat_id,
            "❌ **Город или аэропорт не найден.** Попробуй написать название иначе (например: *Скиатос*, *Париж*, *Милан*):",
            parse_mode="Markdown"
        )
        return
        
    user_states[chat_id]['to'] = code
    user_states[chat_id]['step'] = 'DATES'
    
    bot.send_message(
        chat_id,
        f"✅ Направление: **{name} ({code})**\n\n"
        "**Шаг 3 из 3:** Введи желаемые даты поездки (например: *10.05.2027 - 17.05.2027*):",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'DATES')
def get_dates(message):
    chat_id = message.chat.id
    dates = message.text.strip()
    
    dep = user_states[chat_id]['from']
    arr = user_states[chat_id]['to']
    
    add_subscription(chat_id, dep, arr, dates)
    user_states[chat_id]['step'] = None
    
    bot.send_message(
        chat_id,
        f"🎯 **Подписка сохранена!**\n\n"
        f"✈️ Маршрут: **{dep} ➔ {arr}**\n"
        f"📅 Даты: `{dates}`\n\n"
        f"🔍 Бот начал мониторинг через агрегатор цен. Как только цена станет минимальной — пришлем уведомление со ссылкой!",
        parse_mode="Markdown"
    )

# ==================== ФОНОВЫЙ МОНИТОРИНГ ЦЕН ====================
def check_prices_task():
    while True:
        try:
            time.sleep(3600) # Каждый час
            subs = get_all_subscriptions()
            
            for sub in subs:
                sub_id, chat_id, dep, arr, dates, last_price = sub
                
                try:
                    # Запрос актуальных цен через легкий эндпоинт агрегатора
                    url = f"https://prices.gis.travelpayouts.com/v2/prices/latest?origin={dep}&destination={arr}&currency=eur"
                    res = requests.get(url, timeout=10).json()
                    
                    price = None
                    if res.get("data") and len(res["data"]) > 0:
                        price = res["data"][0].get("value")
                    
                    if price:
                        if last_price is None:
                            update_subscription_price(sub_id, price)
                        elif price < last_price:
                            update_subscription_price(sub_id, price)
                            
                            wizz_url = f"https://wizzair.com/ru-ru/flights/{dep.lower()}/{arr.lower()}"
                            markup = types.InlineKeyboardMarkup()
                            markup.add(types.InlineKeyboardButton("🔥 Забронировать рейс", url=wizz_url))
                            
                            bot.send_message(
                                chat_id,
                                f"🚨 **ЦЕНА УПАЛА!** 📉\n\n"
                                f"✈️ Маршрут: **{dep} ➔ {arr}**\n"
                                f"📅 Даты: `{dates}`\n"
                                f"💵 Новая цена: **{price} EUR** (была {last_price} EUR)\n\n"
                                f"Успей забронировать рейс по отличной цене!",
                                reply_markup=markup,
                                parse_mode="Markdown"
                            )
                except Exception as e:
                    print(f"Ошибка проверки цен для {dep}-{arr}: {e}")
                    
        except Exception as e:
            print(f"Ошибка фонового процесса: {e}")

monitor_thread = threading.Thread(target=check_prices_task, daemon=True)
monitor_thread.start()

# ==================== FLASK SERVER ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Wizz Air Tracker is running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.start()
    
    print("Бот запущен с автоматическим API городов...")
    bot.infinity_polling(skip_pending=True)
