import telebot
from telebot import types
import json
import os
import time
import asyncio
from telethon import TelegramClient, functions
from telethon.errors import (
    PeerIdInvalidError, FloodWaitError, AuthKeyError,
    AuthKeyUnregisteredError, UserDeactivatedError, RPCError
)
import glob
from datetime import datetime, timedelta
import logging
import threading

# Конфигурация
BOT_TOKEN = "8076809934:AAEI9mNl1vNDSoISXO4Y-bEkkvLtA5K8h9I"
CRYPTO_PAY_TOKEN = "357259:AAIQ8eTVkkYcT5O2Ev1oJYniCHtFLKHhm6j"  
#Замените на ваш токен CryptoBot
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
ADMIN_ID = 426217102
COOLDOWN_MINUTES = 15
MAX_CONCURRENT_SESSIONS = 2

# Инициализация
bot = telebot.TeleBot(BOT_TOKEN)

# Файлы и папки
DATABASE_FILE = "datab123ase.json"
SESSIONS_FOLDER = "sessions"
LOGS_FOLDER = "logs"
INVALID_SESSIONS_FILE = "invalid_sessions.json"

# Создание папок
for folder in [SESSIONS_FOLDER, LOGS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Настройка логирования
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Состояния пользователей
user_states = {}
payment_data = {}
session_upload_count = {}

def load_database():
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {
                "users": {},
                "subscriptions": {},
                "cooldowns": {}
            }
    return {
        "users": {},
        "subscriptions": {},
        "cooldowns": {}
    }

def save_database(data):
    try:
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения БД: {e}")

def load_invalid_sessions():
    """Загрузка списка невалидных сессий"""
    if os.path.exists(INVALID_SESSIONS_FILE):
        try:
            with open(INVALID_SESSIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_invalid_sessions(invalid_list):
    """Сохранение списка невалидных сессий"""
    try:
        with open(INVALID_SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(invalid_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения невалидных сессий: {e}")

def add_invalid_session(session_name):
    """Добавление сессии в список невалидных"""
    invalid_sessions = load_invalid_sessions()
    if session_name not in invalid_sessions:
        invalid_sessions.append(session_name)
        save_invalid_sessions(invalid_sessions)

def get_total_sessions():
    """Получение общего количества сессий"""
    session_files = glob.glob(os.path.join(SESSIONS_FOLDER, "*.session"))
    return len(session_files)

def clean_invalid_sessions():
    """Очистка невалидных сессий"""
    invalid_sessions = load_invalid_sessions()
    removed_count = 0
    
    for session_name in invalid_sessions:
        session_path = os.path.join(SESSIONS_FOLDER, f"{session_name}.session")
        if os.path.exists(session_path):
            try:
                os.remove(session_path)
                removed_count += 1
            except Exception as e:
                logger.error(f"Ошибка удаления сессии {session_name}: {e}")
    
    # Очищаем список невалидных сессий
    save_invalid_sessions([])
    return removed_count

db = load_database()

def has_active_subscription(user_id):
    """Проверка активной подписки"""
    user_id_str = str(user_id)
    if user_id_str not in db["subscriptions"]:
        return False
    
    sub = db["subscriptions"][user_id_str]
    if sub["type"] == "forever":
        return True
    
    expiry = datetime.fromisoformat(sub["expires_at"])
    return datetime.now() < expiry

def get_subscription_info(user_id):
    """Получение информации о подписке"""
    user_id_str = str(user_id)
    if user_id_str not in db["subscriptions"]:
        return "Отсутствует"
    
    sub = db["subscriptions"][user_id_str]
    if sub["type"] == "forever":
        return "Навсегда"
    
    expiry = datetime.fromisoformat(sub["expires_at"])
    if datetime.now() >= expiry:
        # Удаляем истекшую подписку
        del db["subscriptions"][user_id_str]
        save_database(db)
        return "Отсутствует"
    
    days_left = (expiry - datetime.now()).days + 1
    return f"{days_left} дней"

def add_subscription(user_id, days):
    """Добавление подписки"""
    user_id_str = str(user_id)
    
    if days == "forever":
        db["subscriptions"][user_id_str] = {
            "type": "forever",
            "expires_at": None
        }
    else:
        current_time = datetime.now()
        
        # Если есть активная подписка, добавляем к ней
        if user_id_str in db["subscriptions"] and has_active_subscription(user_id):
            if db["subscriptions"][user_id_str]["type"] == "forever":
                return  # Уже навсегда
            
            current_expiry = datetime.fromisoformat(db["subscriptions"][user_id_str]["expires_at"])
            if current_expiry > current_time:
                current_time = current_expiry
        
        new_expiry = current_time + timedelta(days=int(days))
        db["subscriptions"][user_id_str] = {
            "type": "days",
            "expires_at": new_expiry.isoformat()
        }
    
    save_database(db)

async def create_crypto_client():
    """Создание клиента CryptoBot в async контексте"""
    try:
        from aiocryptopay import AioCryptoPay, Networks
        crypto = AioCryptoPay(token=CRYPTO_PAY_TOKEN, network=Networks.MAIN_NET)
        return crypto
    except Exception as e:
        logger.error(f"Ошибка создания crypto клиента: {e}")
        return None

def safe_edit_message(chat_id, message_id, text, parse_mode=None, reply_markup=None):
    """Безопасное редактирование сообщения"""
    try:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        return True
    except Exception as e:
        if "message is not modified" not in str(e):
            logger.error(f"Ошибка редактирования сообщения: {e}")
        return False

# ==================== ПАНЕЛЬ УПРАВЛЕНИЯ СЕССИЯМИ ====================

@bot.message_handler(commands=['sessions'])
def sessions_panel(message):
    """Панель управления сессиями"""
    try:
        if message.from_user.id != ADMIN_ID:
            bot.reply_to(message, "❌ У вас нет прав")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        add_btn = types.InlineKeyboardButton("Добавить", callback_data="sessions_add")
        clean_btn = types.InlineKeyboardButton("Очистить", callback_data="sessions_clean")
        
        markup.add(add_btn, clean_btn)
        
        total_sessions = get_total_sessions()
        invalid_sessions = len(load_invalid_sessions())
        
        panel_text = f"<b>Панель управления сессиями</b>\n\n📊 <b>Всего сессий:</b> <code>{total_sessions}</code>\n❌ <b>Невалидных:</b> <code>{invalid_sessions}</code>"
        
        bot.send_message(
            message.chat.id,
            panel_text,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Ошибка панели сессий: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "sessions_add")
def sessions_add_handler(call):
    """Обработчик добавления сессий"""
    try:
        if call.from_user.id != ADMIN_ID:
            return
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            "<b>Скиньте файлы session Telethon</b>\n\n<b>Для остановки принятие файлов напишите /stop</b>",
            parse_mode='HTML'
        )
        
        user_states[call.from_user.id] = "uploading_sessions"
        session_upload_count[call.from_user.id] = 0
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка добавления сессий: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "sessions_clean")
def sessions_clean_handler(call):
    """Обработчик очистки невалидных сессий"""
    try:
        if call.from_user.id != ADMIN_ID:
            return
        
        removed_count = clean_invalid_sessions()
        total_sessions = get_total_sessions()
        
        clean_text = f"🧹 <b>Очистка завершена</b>\n\n❌ <b>Удалено невалидных:</b> <code>{removed_count}</code>\n📊 <b>Осталось сессий:</b> <code>{total_sessions}</code>"
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            clean_text,
            parse_mode='HTML'
        )
        
        bot.answer_callback_query(call.id, f"✅ Удалено {removed_count} невалидных сессий")
        
    except Exception as e:
        logger.error(f"Ошибка очистки сессий: {e}")

@bot.message_handler(commands=['stop'])
def stop_upload_handler(message):
    """Остановка загрузки сессий"""
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        if message.from_user.id in user_states and user_states[message.from_user.id] == "uploading_sessions":
            uploaded_count = session_upload_count.get(message.from_user.id, 0)
            total_sessions = get_total_sessions()
            
            success_text = f"✅ <b>Успешно добавлено:</b> <code>{uploaded_count}</code>\n\n<b>Всего сессий в боте:</b> <code>{total_sessions}</code>"
            
            bot.send_message(
                message.chat.id,
                success_text,
                parse_mode='HTML'
            )
            
            # Очищаем состояние
            del user_states[message.from_user.id]
            if message.from_user.id in session_upload_count:
                del session_upload_count[message.from_user.id]
        
    except Exception as e:
        logger.error(f"Ошибка остановки загрузки: {e}")

@bot.message_handler(content_types=['document'])
def handle_session_upload(message):
    """Обработчик загрузки файлов сессий"""
    try:
        if message.from_user.id != ADMIN_ID:
            return
        
        if message.from_user.id not in user_states or user_states[message.from_user.id] != "uploading_sessions":
            return
        
        # Проверяем, что это .session файл
        if not message.document.file_name.endswith('.session'):
            bot.reply_to(message, "❌ Принимаются только .session файлы")
            return
        
        try:
            # Скачиваем файл
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Сохраняем в папку sessions
            file_path = os.path.join(SESSIONS_FOLDER, message.document.file_name)
            
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)
            
            # Увеличиваем счетчик
            session_upload_count[message.from_user.id] += 1
            
            bot.reply_to(message, f"✅ Файл {message.document.file_name} добавлен")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка сохранения файла: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка загрузки сессии: {e}")

# ==================== ОСНОВНОЙ КОД (НЕ ИЗМЕНЕН) ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or "пользователь"
        
        # Сохраняем пользователя в БД
        db["users"][str(user_id)] = {
            "username": username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }
        save_database(db)
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        send_btn = types.InlineKeyboardButton("🚀 Отправить", callback_data="send_report")
        profile_btn = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
        prices_btn = types.InlineKeyboardButton("‼️ Цены", callback_data="prices")
        channel_btn = types.InlineKeyboardButton("🗂 Канал", url="https://t.me/+5fUExPKEJn5mYWMy")
        
        markup.add(send_btn)
        markup.add(profile_btn, prices_btn)
        markup.add(channel_btn)
        
        welcome_text = f"🌟 <b>Добро пожаловать <a href='tg://user?id={user_id}'>{username}</a></b>\n\n<blockquote>Самая вкусная и горячая пицца только у нас </blockquote>"
        
        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Ошибка start: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "profile")
def show_profile(call):
    try:
        user_id = call.from_user.id
        subscription_info = get_subscription_info(user_id)
        
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("< Назад", callback_data="back_to_main")
        markup.add(back_btn)
        
        profile_text = f"👤 <b>Ваш профиль:</b>\n\n🆔 <b>Айди:</b> <code>{user_id}</code>\n🗃️ <b>Подписка:</b> <code>{subscription_info}</code>"
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            profile_text,
            parse_mode='HTML',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка профиля: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "prices")
def show_prices(call):
    try:
        markup = types.InlineKeyboardMarkup(row_width=2)
        day1_btn = types.InlineKeyboardButton("1 день", callback_data="buy_1")
        day3_btn = types.InlineKeyboardButton("3 дня", callback_data="buy_3")
        day7_btn = types.InlineKeyboardButton("7 дней", callback_data="buy_7")
        forever_btn = types.InlineKeyboardButton("Навсегда", callback_data="buy_forever")
        back_btn = types.InlineKeyboardButton("<< Назад", callback_data="back_to_main")
        
        markup.add(day1_btn, day3_btn)
        markup.add(day7_btn, forever_btn)
        markup.add(back_btn)
        
        prices_text = "<b>Цены на самую вкусную пиццу</b> \n\n <b>шашлык:</b>\n<blockquote>1 день - 1.2 $\n3 дня - 2.5 $\n7 дней - 4.5 $\nНавсегда - 8 $</blockquote>"
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            prices_text,
            parse_mode='HTML',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка цен: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def create_invoice(call):
    try:
        plan = call.data.split("_")[1]
        user_id = call.from_user.id
        
        prices = {
            "1": {"amount": 2, "days": 1, "name": "1 день"},
            "3": {"amount": 2.5, "days": 3, "name": "3 дня"},
            "7": {"amount": 4.5, "days": 7, "name": "7 дней"},
            "forever": {"amount": 8.0, "days": "forever", "name": "Навсегда"}
        }
        
        if plan not in prices:
            return
        
        price_info = prices[plan]
        
        def create_payment():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            crypto = None
            try:
                crypto = loop.run_until_complete(create_crypto_client())
                if not crypto:
                    safe_edit_message(
                        call.message.chat.id,
                        call.message.message_id,
                        "❌ Ошибка инициализации платежной системы"
                    )
                    return
                
                invoice = loop.run_until_complete(
                    crypto.create_invoice(
                        asset="USDT",
                        amount=price_info["amount"]
                    )
                )
                
                # Получаем правильный URL для оплаты
                pay_url = None
                if hasattr(invoice, 'bot_invoice_url'):
                    pay_url = invoice.bot_invoice_url
                elif hasattr(invoice, 'mini_app_invoice_url'):
                    pay_url = invoice.mini_app_invoice_url
                elif hasattr(invoice, 'pay_url'):
                    pay_url = invoice.pay_url
                else:
                    # Создаем URL вручную
                    pay_url = f"https://t.me/CryptoBot?start=invoice_{invoice.invoice_id}"
                
                payment_data[user_id] = {
                    "invoice_id": invoice.invoice_id,
                    "days": price_info["days"],
                    "plan_name": price_info["name"]
                }
                
                markup = types.InlineKeyboardMarkup()
                pay_btn = types.InlineKeyboardButton("🔗 Счёт", url=pay_url)
                check_btn = types.InlineKeyboardButton("🔍 Проверить", callback_data=f"check_payment_{invoice.invoice_id}")
                markup.add(pay_btn, check_btn)
                
                invoice_text = f"🦋 <b>Создан счёт</b> | <code>{price_info['name']}</code>"
                
                safe_edit_message(
                    call.message.chat.id,
                    call.message.message_id,
                    invoice_text,
                    parse_mode='HTML',
                    reply_markup=markup
                )
                
            except Exception as e:
                safe_edit_message(
                    call.message.chat.id,
                    call.message.message_id,
                    f"❌ Ошибка создания счета: {str(e)[:100]}"
                )
            finally:
                if crypto and hasattr(crypto, 'close'):
                    try:
                        loop.run_until_complete(crypto.close())
                    except:
                        pass
                loop.close()
        
        thread = threading.Thread(target=create_payment)
        thread.daemon = True
        thread.start()
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка создания счета: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_payment_"))
def check_payment(call):
    try:
        user_id = call.from_user.id
        
        if user_id not in payment_data:
            bot.answer_callback_query(call.id, "❌ Данные платежа не найдены")
            return
        
        def check_invoice():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            crypto = None
            try:
                crypto = loop.run_until_complete(create_crypto_client())
                if not crypto:
                    bot.answer_callback_query(call.id, "❌ Ошибка платежной системы")
                    return
                
                invoice_id = payment_data[user_id]["invoice_id"]
                invoices = loop.run_until_complete(crypto.get_invoices(invoice_ids=[invoice_id]))
                
                if invoices and invoices[0].status == "paid":
                    days = payment_data[user_id]["days"]
                    add_subscription(user_id, days)
                    
                    success_text = "❤️ <b>Спасибо за покупку подписки</b>\n\n<code>Вам успешно выдана подписка</code>"
                    
                    markup = types.InlineKeyboardMarkup()
                    back_btn = types.InlineKeyboardButton("< Назад", callback_data="back_to_main")
                    markup.add(back_btn)
                    
                    safe_edit_message(
                        call.message.chat.id,
                        call.message.message_id,
                        success_text,
                        parse_mode='HTML',
                        reply_markup=markup
                    )
                    
                    del payment_data[user_id]
                else:
                    bot.answer_callback_query(call.id, "❌ Оплата не найдена")
                    
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
            finally:
                if crypto and hasattr(crypto, 'close'):
                    try:
                        loop.run_until_complete(crypto.close())
                    except:
                        pass
                loop.close()
        
        thread = threading.Thread(target=check_invoice)
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        logger.error(f"Ошибка проверки платежа: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main(call):
    try:
        user_id = call.from_user.id
        username = call.from_user.username or "пользователь"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        send_btn = types.InlineKeyboardButton("🚀 Отправить", callback_data="send_report")
        profile_btn = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
        prices_btn = types.InlineKeyboardButton("‼️ Цены", callback_data="prices")
        channel_btn = types.InlineKeyboardButton("🗂 Канал", url="https://t.me/+e3GB0pXvOWs1N2Ri")
        
        markup.add(send_btn)
        markup.add(profile_btn, prices_btn)
        markup.add(channel_btn)
        
        welcome_text = f"🌟 <b>Добро пожаловать <a href='tg://user?id={user_id}'>{username}</a></b>\n\n<blockquote>Самый вкусный и горячая пицца🍕 только у нас</blockquote>"
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            welcome_text,
            parse_mode='HTML',
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка возврата в меню: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "send_report")
def handle_send_button(call):
    try:
        user_id = call.from_user.id
        
        if not has_active_subscription(user_id):
            bot.answer_callback_query(call.id, "❌ Без подписки нельзя")
            return
        
        # Проверка кулдауна
        if str(user_id) in db["cooldowns"]:
            last_use = datetime.fromisoformat(db["cooldowns"][str(user_id)])
            if datetime.now() < last_use + timedelta(minutes=COOLDOWN_MINUTES):
                remaining = (last_use + timedelta(minutes=COOLDOWN_MINUTES) - datetime.now()).seconds // 60 + 1
                bot.answer_callback_query(call.id, f"⏰ Подождите {remaining} минут")
                return
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            "🔗 <b>Введите ссылку на нарушение</b>\n\n"
            "📝 <i>Формат:</i> <code>https://t.me/username/123</code>\n"
            "⚡ <i>Система готова к быстрой обработке</i>",
            parse_mode='HTML'
        )
        
        user_states[user_id] = "waiting_for_link"
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Ошибка кнопки отправить: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка")

def is_valid_telegram_link(link: str) -> bool:
    """Проверка валидности Telegram ссылки"""
    if not link:
        return False
    
    if link.startswith('https://t.me/') and '/' in link[13:]:
        parts = link.rstrip('/').split('/')
        if len(parts) >= 4 and parts[-1].isdigit():
            return True
    return False

@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id] == "waiting_for_link")
def handle_link_input(message):
    try:
        user_id = message.from_user.id
        link = message.text.strip()
        
        del user_states[user_id]
        
        if not is_valid_telegram_link(link):
            bot.send_message(
                message.chat.id,
                "❌ <b>Некорректная ссылка</b>\n\n"
                "📝 <i>Нужен формат:</i> <code>https://t.me/username/123</code>",
                parse_mode='HTML'
            )
            return
        
        
        status_msg = bot.send_message(
            message.chat.id,
            "🚀 <b>Запуск системы жалоб...</b>\n"
            "⚡ <i>Инициализация параллельной обработки</i>",
            parse_mode='HTML'
        )
        
        # Установка кулдауна
        db["cooldowns"][str(user_id)] = datetime.now().isoformat()
        save_database(db)
        
        def run_reports():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_reports(message.chat.id, link, status_msg.message_id))
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")
                safe_edit_message(
                    message.chat.id,
                    status_msg.message_id,
                    f"❌ <b>Критическая ошибка:</b> {str(e)[:100]}",
                    parse_mode='HTML'
                )
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_reports)
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        logger.error(f"Ошибка обработки ссылки: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "close_warning")
def close_warning(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка закрытия предупреждения: {e}")

# Админ панель
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    try:
        if message.from_user.id != ADMIN_ID:
            bot.reply_to(message, "❌ У вас нет прав")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        give_btn = types.InlineKeyboardButton("🗃️ Выдать", callback_data="admin_give")
        take_btn = types.InlineKeyboardButton("📂 Забрать", callback_data="admin_take")
        broadcast_btn = types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")
        
        markup.add(give_btn, take_btn)
        markup.add(broadcast_btn)
        
        bot.send_message(
            message.chat.id,
            "⚙ <b>Админ панель</b>",
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Ошибка админ панели: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_give")
def admin_give_subscription(call):
    try:
        if call.from_user.id != ADMIN_ID:
            return
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            "Введите айди пользователя:"
        )
        
        user_states[call.from_user.id] = "admin_waiting_user_id_give"
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка выдачи подписки: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_take")
def admin_take_subscription(call):
    try:
        if call.from_user.id != ADMIN_ID:
            return
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            "Введите айди пользователя:"
        )
        
        user_states[call.from_user.id] = "admin_waiting_user_id_take"
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка забирания подписки: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast(call):
    try:
        if call.from_user.id != ADMIN_ID:
            return
        
        safe_edit_message(
            call.message.chat.id,
            call.message.message_id,
            "Введите текст рассылки:"
        )
        
        user_states[call.from_user.id] = "admin_waiting_broadcast_text"
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")

@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and message.from_user.id in user_states)
def handle_admin_states(message):
    try:
        state = user_states[message.from_user.id]
        
        if state == "admin_waiting_user_id_give":
            try:
                target_user_id = int(message.text)
                user_states[message.from_user.id] = f"admin_waiting_days_{target_user_id}"
                bot.send_message(message.chat.id, "Введите количество дней (или 'forever' для навсегда):")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Неверный формат ID")
                del user_states[message.from_user.id]
        
        elif state.startswith("admin_waiting_days_"):
            target_user_id = int(state.split("_")[-1])
            days = message.text.strip()
            
            if days == "forever":
                add_subscription(target_user_id, "forever")
                bot.send_message(message.chat.id, f"✅ Выдана подписка навсегда пользователю {target_user_id}")
            else:
                try:
                    days_int = int(days)
                    add_subscription(target_user_id, days_int)
                    bot.send_message(message.chat.id, f"✅ Выдана подписка на {days_int} дней пользователю {target_user_id}")
                except ValueError:
                    bot.send_message(message.chat.id, "❌ Неверный формат дней")
            
            del user_states[message.from_user.id]
        
        elif state == "admin_waiting_user_id_take":
            try:
                target_user_id = int(message.text)
                if str(target_user_id) in db["subscriptions"]:
                    del db["subscriptions"][str(target_user_id)]
                    save_database(db)
                    bot.send_message(message.chat.id, f"✅ Подписка забрана у пользователя {target_user_id}")
                else:
                    bot.send_message(message.chat.id, f"❌ У пользователя {target_user_id} нет подписки")
                del user_states[message.from_user.id]
            except ValueError:
                bot.send_message(message.chat.id, "❌ Неверный формат ID")
                del user_states[message.from_user.id]
        
        elif state == "admin_waiting_broadcast_text":
            broadcast_text = message.text
            
            sent = 0
            failed = 0
            
            for user_id in db["users"]:
                try:
                    bot.send_message(int(user_id), broadcast_text, parse_mode='HTML')
                    sent += 1
                    time.sleep(0.1)  # Избегаем лимитов
                except:
                    failed += 1
            
            bot.send_message(
                message.chat.id,
                f"📢 <b>Рассылка завершена</b>\n"
                f"✅ Отправлено: {sent}\n"
                f"❌ Не отправлено: {failed}",
                parse_mode='HTML'
            )
            del user_states[message.from_user.id]
    
    except Exception as e:
        logger.error(f"Ошибка админ состояний: {e}")

# Функции для отправки жалоб
async def get_target_info(username: str, msg_id: int):
    """Получение информации о цели"""
    try:
        session_files = [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith('.session')]
        if not session_files:
            return "Неизвестно", "Неизвестно"
        
        session_path = os.path.join(SESSIONS_FOLDER, session_files[0])
        client = TelegramClient(session_path, API_ID, API_HASH)
        
        try:
            await asyncio.wait_for(client.connect(), timeout=10)
            
            if not await asyncio.wait_for(client.is_user_authorized(), timeout=5):
                return "Неизвестно", "Неизвестно"
            
            peer = await asyncio.wait_for(client.get_input_entity(username), timeout=10)
            entity = await asyncio.wait_for(client.get_entity(peer), timeout=10)
            
            if hasattr(entity, 'title'):
                target_name = entity.title
            elif hasattr(entity, 'first_name'):
                target_name = entity.first_name
                if hasattr(entity, 'last_name') and entity.last_name:
                    target_name += f" {entity.last_name}"
            else:
                target_name = username
            
            target_id = entity.id
            return target_name, target_id
        
        finally:
            if client.is_connected():
                await client.disconnect()
    
    except Exception:
        return username, "Неизвестно"

async def send_reports(chat_id: int, link: str, status_msg_id: int):
    """Быстрая параллельная отправка жалоб"""
    
    # Парсинг ссылки
    username, msg_id = link.rstrip('/').split('/')[-2:]
    msg_id = int(msg_id)
    
    # Получение информации о цели
    safe_edit_message(
        chat_id,
        status_msg_id,
        "🔍 <b>Анализ цели...</b>\n"
        "📊 <i>Получение информации о канале/пользователе</i>",
        parse_mode='HTML'
    )
    
    target_name, target_id = await get_target_info(username, msg_id)
    
    # Получение всех сессий
    session_files = [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith('.session')]
    
    if not session_files:
        safe_edit_message(
            chat_id,
            status_msg_id,
            "❌ <b>Ошибка:</b> Нет сессий в папке sessions",
            parse_mode='HTML'
        )
        return
    
    # Обновление статуса
    safe_edit_message(
        chat_id,
        status_msg_id,
        f"⚡ <b>Параллельная обработка запущена</b>\n\n"
        f"🎯 <b>Цель:</b> <code>{target_name}</code>\n"
        f"🆔 <b>ID:</b> <code>{target_id}</code>\n"
        f"📝 <b>Сообщение:</b> <code>{msg_id}</code>\n"
        f"🔄 <b>Сессий в обработке:</b> <code>{len(session_files)}</code>\n"
        f"⚙️ <b>Параллельность:</b> <code>{MAX_CONCURRENT_SESSIONS}</code>",
        parse_mode='HTML'
    )
    
    sent = 0
    fail = 0
    logs = []
    
    # Семафор для контроля параллельности
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SESSIONS)
    
    async def process_session(session_file):
        async with semaphore:
            session_path = os.path.join(SESSIONS_FOLDER, session_file)
            session_name = session_file[:-8]
            
            client = TelegramClient(session_path, API_ID, API_HASH)
            
            try:
                await asyncio.wait_for(client.connect(), timeout=10)
                
                if not await asyncio.wait_for(client.is_user_authorized(), timeout=8):
                    # Добавляем в список невалидных
                    add_invalid_session(session_name)
                    return session_name, False, "не авторизован"
                
                await asyncio.wait_for(client.get_dialogs(), timeout=10)
                peer = await asyncio.wait_for(client.get_input_entity(username), timeout=8)
                
                messages = await asyncio.wait_for(client.get_messages(peer, ids=msg_id), timeout=8)
                if not messages:
                    raise ValueError("Сообщение не найдено")
                
                await asyncio.wait_for(
                    client(functions.messages.ReportSpamRequest(peer=peer)),
                    timeout=10
                )
                
                return session_name, True, "успешно"
            
            except asyncio.TimeoutError:
                return session_name, False, "таймаут"
            except ValueError as e:
                return session_name, False, f"сообщение не найдено"
            except PeerIdInvalidError:
                return session_name, False, "неверный peer"
            except FloodWaitError as e:
                return session_name, False, f"FloodWait: {e.seconds}s"
            except (AuthKeyError, AuthKeyUnregisteredError, UserDeactivatedError):
                # Добавляем в список невалидных
                add_invalid_session(session_name)
                return session_name, False, "невалидная сессия"
            except Exception as e:
                return session_name, False, f"ошибка: {str(e)[:30]}"
            finally:
                try:
                    if client.is_connected():
                        await asyncio.wait_for(client.disconnect(), timeout=3)
                except:
                    pass
    
    # Параллельная обработка всех сессий
    tasks = [process_session(sf) for sf in session_files]
    
    completed = 0
    for coro in asyncio.as_completed(tasks):
        try:
            result = await coro
            completed += 1
            
            session_name, success, message = result
            if success:
                sent += 1
                logs.append(f'✅ {session_name}: Жалоба отправлена')
            else:
                fail += 1
                logs.append(f'❌ {session_name}: {message}')
            
            # Обновление прогресса каждые 10 сессий
            if completed % 10 == 0 or completed == len(session_files):
                progress = (completed / len(session_files)) * 100
                safe_edit_message(
                    chat_id,
                    status_msg_id,
                    f"⚡ <b>Обработка в процессе...</b>\n\n"
                    f"🎯 <b>Цель:</b> <code>{target_name}</code>\n"
                    f"🆔 <b>ID:</b> <code>{target_id}</code>\n"
                    f"📝 <b>Сообщение:</b> <code>{msg_id}</code>\n\n"
                    f"📊 <b>Прогресс:</b> <code>{completed}/{len(session_files)}</code> ({progress:.1f}%)\n"
                    f"✅ <b>Успешно:</b> <code>{sent}</code>\n"
                    f"❌ <b>Ошибок:</b> <code>{fail}</code>",
                    parse_mode='HTML'
                )
        
        except Exception as e:
            fail += 1
            logs.append(f'❌ task_error: {str(e)[:30]}')
    
    # Создание красивого отчета
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    success_rate = (sent / len(session_files)) * 100 if session_files else 0
    
    # Создание детального лог файла
    log_content = f"""╔══════════════════════════════════════════════════════════════╗
║                    📊 ОТЧЕТ О ЖАЛОБАХ                        ║
╠══════════════════════════════════════════════════════════════╣
║ 🕐 Время:           {timestamp}                    ║
║ 🎯 Цель:            {target_name:<30}           ║
║ 🆔 Target ID:       {target_id:<30}           ║
║ 📝 Сообщение ID:    {msg_id:<30}           ║
║ 🔗 Ссылка:          {link:<30}           ║
╠══════════════════════════════════════════════════════════════╣
║ 📈 СТАТИСТИКА                                                ║
║ 📊 Всего сессий:    {len(session_files):<30}           ║
║ ✅ Успешно:         {sent:<30}           ║
║ ❌ Неудачно:        {fail:<30}           ║
║ 📊 Успешность:      {success_rate:.1f}%{' ':<25}           ║
║ ⚡ Параллельность:  {MAX_CONCURRENT_SESSIONS:<30}           ║
╚══════════════════════════════════════════════════════════════╝

📋 ДЕТАЛЬНЫЙ ЛОГ:
{'='*60}
"""
    
    for log in logs:
        log_content += f"{log}\n"
    
    log_content += f"\n{'='*60}\n"
    log_content += f"📊 ИТОГО: Отправлено: {sent} | Не отправлено: {fail}\n"
    log_content += f"⚡ Время обработки: ~{len(session_files)//MAX_CONCURRENT_SESSIONS + 1} секунд\n"
    
    # Сохранение и отправка отчета
    log_filename = os.path.join(LOGS_FOLDER, f'report_{int(time.time())}.txt')
    
    try:
        with open(log_filename, 'w', encoding='utf-8') as f:
            f.write(log_content)
        
        # Красивый caption для файла
        caption = f"""🎯 <b>ОТЧЕТ ГОТОВ!</b>

📊 <b>Статистика:</b>
├ 🎯 Цель: <code>{target_name}</code>
├ 🆔 ID: <code>{target_id}</code>
├ 📝 Сообщение: <code>{msg_id}</code>
├ ✅ Отправлено: <code>{sent}</code>
├ ❌ Ошибок: <code>{fail}</code>
└ 📈 Успешность: <code>{success_rate:.1f}%</code>

⏰ <b>Кулдаун:</b> 15 минут
⚡ <b>Скорость:</b> ~{len(session_files)//MAX_CONCURRENT_SESSIONS + 1} сек"""
        
        with open(log_filename, 'rb') as f:
            bot.send_document(
                chat_id,
                f,
                caption=caption,
                parse_mode='HTML'
            )
        
        os.remove(log_filename)
    
    except Exception as e:
        bot.send_message(
            chat_id,
            f"❌ <b>Ошибка создания отчета:</b> {str(e)[:100]}",
            parse_mode='HTML'
        )

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    if message.from_user.id not in user_states:
        bot.reply_to(message, "Используйте /start")

def run_bot():
    retry_count = 0
    max_retries = 10
    
    while retry_count < max_retries:
        try:
            print("🤖 Бот запущен...")
            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=20,
                skip_pending=True,
                none_stop=True
            )
            break
        except Exception as e:
            retry_count += 1
            wait_time = min(retry_count * 5, 60)
            print(f"❌ Ошибка ({retry_count}/{max_retries}): {e}")
            
            if retry_count < max_retries:
                print(f"🔄 Переподключение через {wait_time}с...")
                time.sleep(wait_time)
            else:
                print("💀 Превышено количество попыток")
                break

if __name__ == "__main__":
    try:
        if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            print("❌ Установите BOT_TOKEN")
            exit(1)
        
        if CRYPTO_PAY_TOKEN == "YOUR_CRYPTO_PAY_TOKEN":
            print("❌ Установите CRYPTO_PAY_TOKEN")
            exit(1)
        
        session_files = glob.glob(os.path.join(SESSIONS_FOLDER, "*.session"))
        print(f"📁 Найдено {len(session_files)} сессий")
        
        run_bot()
        
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")