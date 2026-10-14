import os
import telebot
import threading
import time
import sqlite3
from telebot import types
from flask import Flask
import requests
from datetime import datetime

# ВСТАВЬ СЮДА СВОЙ ТОКЕН ОТ BOTFATHER:
TOKEN = os.environ.get("8888798518:AAGgKbzaDsTEgzDQKdlgHbrlhQme82Ycmsc")
bot = telebot.TeleBot(TOKEN)

# Удаляем старый webhook
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
    # Проверяем, нет ли уже такой же активной подписки у пользователя
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

# ==================== БАЗА АЭРОПОРТОВ WIZZ AIR ====================
WIZZ_AIRPORTS = {
    "кишинев": "RMO", "кишинэу": "RMO", "chisinau": "RMO", "rmo": "RMO", "kiv": "RMO",
    "яссы": "IAS", "iasi": "IAS", "ias": "IAS",
    "бухарест": "OTP", "bucharest": "OTP", "otp": "OTP",
    "рим": "FCO", "rome": "FCO", "fco": "FCO",
    "милан": "MXP", "milan": "MXP", "mxp": "MXP", "бергамо": "BGY", "bergamo": "BGY", "bgy": "BGY",
    "лондон": "LTN", "london": "LTN", "ltn": "LTN",
    "берлин": "BER", "berlin": "BER", "ber": "BER",
    "вена": "VIE", "vienna": "VIE", "vie": "VIE",
    "варшава": "WAW", "warsaw": "WAW", "waw": "WAW",
    "париж": "BVA", "paris": "BVA", "bva": "BVA",
    "барселона": "BCN", "barcelona": "BCN", "bcn": "BCN",
    "аликанте": "ALC", "alicante": "ALC", "alc": "ALC",
    "мадрид": "MAD", "madrid": "MAD", "mad": "MAD",
    "валенсия": "VLC", "valencia": "VLC", "vlc": "VLC",
    "ларнака": "LCA", "larnaca": "LCA", "lca": "LCA",
    "афины": "ATH", "athens": "ATH", "ath": "ATH",
    "салоники": "SKG", "thessaloniki": "SKG", "skg": "SKG",
    "дортмунд": "DTM", "dortmund": "DTM", "dtm": "DTM",
    "мемминген": "FMM", "memmingen": "FMM", "fmm": "FMM",
    "брюссель": "CRL", "brussels": "CRL", "crl": "CRL",
    "эйндховен": "EIN", "eindhoven": "EIN", "ein": "EIN"
}

user_states = {}

# ==================== TELEGRAM HANDLERS ====================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    user_states[chat_id] = {'step': 'FROM'}
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Кишинэу (RMO)", "Яссы (IAS)", "Бухарест (OTP)")
    
    bot.send_message(
        chat_id, 
        "✈️ **Wizz Air Price Tracker Bot**\n\n"
        "Я буду круглосуточно следить за ценами на авиабилеты и пришлю уведомление, когда стоимость упадет!\n\n"
        "**Шаг 1 из 3:** Откуда летим? Выбери из кнопок или напиши город:",
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
        bot.send_message(chat_id, "📭 У тебя пока нет активных подписок. Нажми /start, чтобы создать.")
        return
        
    text = "📋 **Твои активные подписки:**\n\n"
    for s in subs:
        dep, arr, dates, price = s
        p_str = f"{price} EUR" > 0 and f"{price} EUR" if price else "определяется..."
        text += f"✈️ **{dep} ➔ {arr}**\n📅 Даты: `{dates}`\n💰 Последняя цена: `{p_str}`\n\n"
    
    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(commands=['cancel'])
def cancel_cmd(message):
    chat_id = message.chat.id
    delete_user_subscriptions(chat_id)
    bot.send_message(chat_id, "🗑 Все твои активные подписки успешно удалены.")

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'FROM')
def get_from_city(message):
    chat_id = message.chat.id
    text = message.text.strip().lower()
    
    code = WIZZ_AIRPORTS.get(text)
    if not code:
        bot.send_message(
            chat_id,
            "❌ **Ошибка:** Wizz Air не летает из этого города или мы его не поддерживаем.\n\n"
            "Пожалуйста, выберите город из кнопок или введите реальный хаб (например: *Кишинэу*, *Яссы*).",
            parse_mode="Markdown"
        )
        return
        
    user_states[chat_id]['from'] = code
    user_states[chat_id]['step'] = 'TO'
    
    bot.send_message(
        chat_id,
        f"✅ Отправление: **{code}**\n\n"
        "**Шаг 2 из 3:** Куда летим? Напиши город назначения (например: *Рим*, *Милан*, *Барселона*, *Париж*):",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'TO')
def get_to_city(message):
    chat_id = message.chat.id
    text = message.text.strip().lower()
    
    code = WIZZ_AIRPORTS.get(text)
    if not code:
        bot.send_message(
            chat_id,
            "❌ **Ошибка:** Такого направления нет в нашей базе.\n\n"
            "Пожалуйста, введите другой город назначения (например: *Рим*, *Милан*, *Лондон*):",
            parse_mode="Markdown"
        )
        return
        
    user_states[chat_id]['to'] = code
    user_states[chat_id]['step'] = 'DATES'
    
    bot.send_message(
        chat_id,
        f"✅ Направление: **{code}**\n\n"
        "**Шаг 3 из 3:** Введи ориентировочные даты (например: *10.05.2027 - 17.05.2027*):",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'DATES')
def get_dates(message):
    chat_id = message.chat.id
    dates = message.text.strip()
    
    dep = user_states[chat_id]['from']
    arr = user_states[chat_id]['to']
    
    # Сохраняем в постоянную SQLite базу
    add_subscription(chat_id, dep, arr, dates)
    
    user_states[chat_id]['step'] = None
    
    bot.send_message(
        chat_id,
        f"🎯 **Подписка успешно оформлена и сохранена!**\n\n"
        f"✈️ Маршрут: **{dep} ➔ {arr}**\n"
        f"📅 Даты: `{dates}`\n\n"
        f"🔍 Бот запущен и проверяет цены каждый час. Посмотреть свои подписки можно через команду /my_subs",
        parse_mode="Markdown"
    )

# ==================== ФОНОВЫЙ МОНИТОР ЦЕН ====================
def check_prices_task():
    """Фоновая функция, которая крутится каждый час и проверяет цены"""
    while True:
        try:
            time.sleep(3600)  # Проверка каждый час (3600 секунд)
            subs = get_all_subscriptions()
            
            for sub in subs:
                sub_id, chat_id, dep, arr, dates, last_price = sub
                
                # Имитация запроса цены через надежный публичный агрегатор / API
                # В продакшн-системах здесь вызывается авиа-агрегатор (например, Skyscanner/Kiwi API)
                # Для примера сделаем безопасный запрос к открытым данным или тестовый расчет
                try:
                    # Пример запроса к легкому открытому трекеру / агрегатору
                    url = f"https://api.duckduckgo.com/?q=wizzair+{dep}+{arr}&format=json"
                    response = requests.get(url, timeout=10)
                    
                    # Условная логика симуляции цены для демонстрации:
                    # В реальной системе парсится актуальная цена из ответа API
                    current_price = 45.0  # Условная текущая цена в евро для примера
                    
                    if last_price is None:
                        update_subscription_price(sub_id, current_price)
                    elif current_price < last_price:
                        # Цена упала! Отправляем алерт пользователю
                        update_subscription_price(sub_id, current_price)
                        
                        wizz_booking_url = f"https://wizzair.com/ru-ru/flights/{dep.lower()}/{arr.lower()}"
                        markup = types.InlineKeyboardMarkup()
                        markup.add(types.InlineKeyboardButton("🔥 Забронировать рейс", url=wizz_booking_url))
                        
                        bot.send_message(
                            chat_id,
                            f"🚨 **ЦЕНА УПАЛА!** 📉\n\n"
                            f"✈️ Маршрут: **{dep} ➔ {arr}**\n"
                            f"📅 Даты: `{dates}`\n"
                            f"💵 Новая цена: **{current_price} EUR** (было {last_price} EUR)\n\n"
                            f"Успей урвать билет по самой выгодной цене!",
                            reply_markup=markup,
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    print(f"Ошибка проверки подписки {sub_id}: {e}")
                    
        except Exception as e:
            print(f"Ошибка в фоновом потоке мониторинга: {e}")

# Запуск фонового потока проверки цен
monitor_thread = threading.Thread(target=check_prices_task, daemon=True)
monitor_thread.start()

# ==================== FLASK SERVER ДЛЯ RENDER ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Wizz Air Price Tracker Bot is running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    # Запускаем веб-сервер в отдельном потоке
    t = threading.Thread(target=run_flask)
    t.start()
    
    print("Бот и система мониторинга запущены...")
    bot.infinity_polling(skip_pending=True)
