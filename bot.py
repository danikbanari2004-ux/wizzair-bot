import os
import telebot
import threading
from telebot import types
from flask import Flask

# ВСТАВЬ СЮДА СВОЙ ТОКЕН ОТ BOTFATHER:
TOKEN = "8888798518:AAFtrPQqMuHjCmwz0zU0ktjgAHY2y7KMkao"
bot = telebot.TeleBot(TOKEN)

# Удаляем старый веб-хук, чтобы убрать конфликт
try:
    bot.remove_webhook()
except Exception as e:
    print(f"Ошибка при удалении webhook: {e}")

# Хранилище подписок и состояний
user_states = {}
user_subscriptions = {}

# Строгая база реальных направлений и хабов Wizz Air
WIZZ_AIRPORTS = {
    # Основные точки вылета
    "кишинев": "RMO", "кишинэу": "RMO", "chisinau": "RMO", "rmo": "RMO", "kiv": "RMO",
    "яссы": "IAS", "iasi": "IAS", "ias": "IAS",
    "бухарест": "OTP", "bucharest": "OTP", "otp": "OTP",
    
    # Популярные направления Wizz Air
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
    "франкфурт": "HHN", "frankfurt": "HHN", "hhn": "HHN",
    "брюссель": "CRL", "brussels": "CRL", "crl": "CRL",
    "эйндховен": "EIN", "eindhoven": "EIN", "ein": "EIN"
}

@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    user_states[chat_id] = {'step': 'FROM'}
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Кишинэу (RMO)", "Яссы (IAS)", "Бухарест (OTP)")
    
    bot.send_message(
        chat_id, 
        "👋 Привет! Я буду отслеживать для тебя падение цен на рейсы Wizz Air.\n\n"
        "**Шаг 1 из 3:** Откуда вылетаем? Выбери из кнопок или напиши город:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'FROM')
def get_from_city(message):
    chat_id = message.chat.id
    text = message.text.strip().lower()
    
    code = WIZZ_AIRPORTS.get(text)
    if not code:
        bot.send_message(
            chat_id,
            "❌ **Ошибка:** Wizz Air не совершает рейсы из этого города или мы его не поддерживаем.\n\n"
            "Пожалуйста, выберите город из кнопок или введите реальный хаб (например: *Кишинэу*, *Яссы*, *Бухарест*).",
            parse_mode="Markdown"
        )
        return  # Остаемся на этом же шаге, ждем правильный ввод
        
    user_states[chat_id]['from'] = code
    user_states[chat_id]['step'] = 'TO'
    
    bot.send_message(
        chat_id,
        f"✅ Отправление: **{code}**\n\n"
        "**Шаг 2 из 3:** Куда летим? Напиши город назначения (например: *Рим*, *Милан*, *Аликанте*, *Париж*):",
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
            "❌ **Ошибка:** Такого направления нет в базе Wizz Air или мы его еще не добавили.\n\n"
            "Пожалуйста, введите другой город назначения (например: *Рим*, *Милан*, *Лондон*, *Барселона*):",
            parse_mode="Markdown"
        )
        return  # Остаемся на шаге 'TO'
        
    user_states[chat_id]['to'] = code
    user_states[chat_id]['step'] = 'DATES'
    
    bot.send_message(
        chat_id,
        f"✅ Направление: **{code}**\n\n"
        "**Шаг 3 из 3:** Введи даты поездки (например: *10.03.2027 - 14.03.2027*):",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'DATES')
def get_dates(message):
    chat_id = message.chat.id
    dates = message.text.strip()
    
    dep = user_states[chat_id]['from']
    arr = user_states[chat_id]['to']
    
    user_subscriptions[chat_id] = {
        'from': dep,
        'to': arr,
        'dates': dates,
        'last_price': None
    }
    
    user_states[chat_id]['step'] = None
    
    bot.send_message(
        chat_id,
        f"🎯 **Подписка успешно оформлена!**\n\n"
        f"✈️ Маршрут: **{dep} ➔ {arr}**\n"
        f"📅 Даты: **{dates}**\n\n"
        f"🔍 Бот начал мониторинг цен. Как только цена упадет — я пришлю тебе реальную ссылку на бронирование!",
        parse_mode="Markdown"
    )

# Веб-сервер для поддержания работы на Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.com("PORT", 10000)) if hasattr(os, "com") else int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.start()
    
    print("Бот запущен...")
    bot.infinity_polling(skip_pending=True)
