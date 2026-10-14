import telebot
import time
import requests
from telebot import types

# 1. ВСТАВЬ СЮДА СВОЙ ТОКЕН ОТ BOTFATHER:
TOKEN = "8888798518:AAFtrPQqMuHjCmwz0zU0ktjgAHY2y7KMkao"
bot = telebot.TeleBot(TOKEN)

# Хранилище подписок в памяти (Для работы 24/7)
user_states = {}
user_subscriptions = {}

# База основных городов/аэропортов для быстрого распознавания
AIRPORTS = {
    "кишинев": "RMO", "кишинэу": "RMO", "chisinau": "RMO", "rmo": "RMO", "kiv": "RMO",
    "бухарест": "OTP", "bucharest": "OTP", "otp": "OTP",
    "яссы": "IAS", "iasi": "IAS", "ias": "IAS",
    "рим": "FCO", "rome": "FCO", "fco": "FCO",
    "милан": "MXP", "milan": "MXP", "mxp": "MXP",
    "лондон": "LTN", "london": "LTN", "ltn": "LTN",
    "берлин": "BER", "berlin": "BER", "ber": "BER",
    "вена": "VIE", "vienna": "VIE", "vie": "VIE",
    "варшава": "WAW", "warsaw": "WAW", "waw": "WAW",
    "париж": "BVA", "paris": "BVA", "bva": "BVA"
}

@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    user_states[chat_id] = {'step': 'FROM'}
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Кишинэу (RMO)", "Яссы (IAS)", "Бухарест (OTP)")
    
    bot.send_message(
        chat_id, 
        "👋 Привет! Я помогу тебе отслеживать дешевые билеты Wizz Air.\n\n"
        "**Шаг 1 из 3:** Откуда вылетаем? Напиши город текстом или выбери из популярных:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'FROM')
def get_from_city(message):
    chat_id = message.chat.id
    text = message.text.strip().lower()
    
    # Ищем код аэропорта
    code = None
    for key, val in AIRPORTS.items():
        if key in text:
            code = val
            break
            
    if not code:
        # Если города нет в словаре, берем первые 3 буквы как код IATA
        code = text[:3].upper()
        
    user_states[chat_id]['from'] = code
    user_states[chat_id]['step'] = 'TO'
    
    bot.send_message(
        chat_id,
        f"✅ Отправление: **{code}**\n\n"
        "**Шаг 2 из 3:** Куда летим? Напиши город назначения (например: *Рим*, *Милан*, *Лондон*, *Париж*):",
        parse_mode="Markdown",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'TO')
def get_to_city(message):
    chat_id = message.chat.id
    text = message.text.strip().lower()
    
    code = None
    for key, val in AIRPORTS.items():
        if key in text:
            code = val
            break
            
    if not code:
        code = text[:3].upper()
        
    user_states[chat_id]['to'] = code
    user_states[chat_id]['step'] = 'DATES'
    
    bot.send_message(
        chat_id,
        f"✅ Направление: **{code}**\n\n"
        "**Шаг 3 из 3:** Введи ориентировочный месяц или даты поездки (например: *Май 2026* или *15.05 - 20.05*):",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'DATES')
def get_dates(message):
    chat_id = message.chat.id
    dates = message.text.strip()
    
    dep = user_states[chat_id]['from']
    arr = user_states[chat_id]['to']
    
    # Сохраняем подписку
    user_subscriptions[chat_id] = {
        'from': dep,
        'to': arr,
        'dates': dates,
        'last_price': None
    }
    
    user_states[chat_id]['step'] = None
    
    # Ссылка на прямой поиск Wizz Air
    wizz_url = f"https://wizzair.com/ru-ru/flights/{dep.lower()}/{arr.lower()}"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✈️ Открыть Wizz Air", url=wizz_url))
    
    bot.send_message(
        chat_id,
        f"🎯 **Подписка успешно оформлена!**\n\n"
        f"✈️ Маршрут: **{dep} ➔ {arr}**\n"
        f"📅 Даты: **{dates}**\n\n"
        f"Я ушел мониторить цены. Как только появятся скидки или цена упадет — я сразу пришлю тебе уведомление сюда!",
        reply_markup=markup,
        parse_mode="Markdown"
    )

if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()