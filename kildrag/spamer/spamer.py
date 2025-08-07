
import telebot
from telebot import types
import sqlite3
import time
import asyncio
import requests
import random
import re
import smtplib
from email.mime.text import MIMEText
import string
import aiohttp
import phonenumbers

TOKEN = "8476985745:AAHI050sxV7mDEjxYWKrdUYZUqC_0qF6W4I"
CHANNEL_ID = -1002530726106
CHANNEL_LINK = "https://t.me/+XFo1yTBtmjcyYTRi"
ADMIN_IDS = [7163004463, 7465411120]
DATABASE_NAME = "spambot.db"
MAIL_FILE = "mails.txt"
BOT_USERNAME = "tg_spamerbot"
REFERRAL_REWARD = 0.05
MIN_WITHDRAWAL = 1

bot = telebot.TeleBot(TOKEN)
conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
cursor = conn.cursor()

# Database functions (create_database, add_user, get_user, is_user_banned, ban_user, unban_user, get_all_users,
# send_message_to_all_users, check_subscription, set_subscription, increase_referral_balance, get_referral_balance,
# add_referral, get_referrals) - same as your code, so I'm skipping it for brevity.  Just make sure these functions
# are all defined.  They're essential to the bot's functionality.  DO NOT OMIT THESE!

def create_database():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            reg_date INTEGER,
            is_admin INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            has_subscription INTEGER DEFAULT 0,
            referral_balance REAL DEFAULT 0.0,
            referrer_id INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER,
            referral_id INTEGER,
            FOREIGN KEY (referrer_id) REFERENCES users(id),
            FOREIGN KEY (referral_id) REFERENCES users(id)
        )
    """)
    conn.commit()
create_database()

def add_user(user_id, username, referrer_id=None):
    cursor.execute("INSERT OR IGNORE INTO users (id, username, reg_date, referrer_id) VALUES (?, ?, ?, ?)", (user_id, username, int(time.time()), referrer_id))
    conn.commit()

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()

def is_user_banned(user_id):
    user = get_user(user_id)
    if user:
        return user[4] == 1
    return False

def ban_user(username):
    cursor.execute("UPDATE users SET banned = 1 WHERE username = ?", (username,))
    conn.commit()

def unban_user(username):
    cursor.execute("UPDATE users SET banned = 0 WHERE username = ?", (username,))
    conn.commit()

def get_all_users():
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()

def send_message_to_all_users(message):
    users = get_all_users()
    for user in users:
        try:
            bot.send_message(user[0], message)
        except Exception as e:
            print(f"Failed to send to user {user[0]}: {e}")

def check_subscription(user_id):
    user = get_user(user_id)
    if user:
        return user[5] == 0
    return True

def set_subscription(username, has_subscription):
    cursor.execute("UPDATE users SET has_subscription = ? WHERE username = ?", (int(has_subscription), username))
    conn.commit()

def increase_referral_balance(user_id, amount):
    cursor.execute("UPDATE users SET referral_balance = referral_balance + ? WHERE id = ?", (amount, user_id))
    conn.commit()

def get_referral_balance(user_id):
    user = get_user(user_id)
    if user:
        return user[6]
    return 0.0

def add_referral(referrer_id, referral_id):
    cursor.execute("INSERT INTO referrals (referrer_id, referral_id) VALUES (?, ?)", (referrer_id, referral_id))
    conn.commit()

def get_referrals(user_id):
    cursor.execute("SELECT referral_id FROM referrals WHERE referrer_id = ?", (user_id,))
    return [row[0] for row in cursor.fetchall()]


def main_menu_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Telegram Spam 😈", callback_data="telegram_spam"))
    markup.add(types.InlineKeyboardButton("SMS Spam 😡", callback_data="sms_spam"))
    markup.add(types.InlineKeyboardButton("Mailer 📧", callback_data="mailer"))
    markup.add(types.InlineKeyboardButton("Профиль 👤", callback_data="profile"))
    markup.add(types.InlineKeyboardButton("Реферальная система 💰", callback_data="referral_system"))
    return markup


def back_button_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Назад 🔙", callback_data="back_to_menu"))
    return markup


def referral_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Вывести", callback_data="withdraw"))
    markup.add(types.InlineKeyboardButton("Назад 🔙", callback_data="back_to_menu"))
    return markup


def subscribe_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("КАНАЛ 🔥", url=CHANNEL_LINK))
    return markup

# CAPTCHA STORAGE
captcha_answers = {}
# MAILER DATA STORAGE
mailer_data = {}

def set_captcha(message_id, answer):
    captcha_answers[message_id] = answer


def get_captcha_answer(message_id):
    return captcha_answers.get(message_id)


def update_captcha(message_id, answer):
    captcha_answers[message_id] = answer


def clear_captcha(message_id):
    if message_id in captcha_answers:
        del captcha_answers[message_id]


# NEW RUSSIAN CAPTCHA
def generate_russian_captcha():
    """Generates a CAPTCHA with a simple arithmetic question in Russian."""
    num1 = random.randint(1, 20)
    num2 = random.randint(1, 20)
    operation = random.choice(['+', '-'])  # Only addition and subtraction for simplicity

    if operation == '+':
        answer = num1 + num2
        question_text = f"Сколько будет {num1} + {num2}?"
    else:
        answer = num1 - num2
        question_text = f"Сколько будет {num1} - {num2}?"

    return question_text, str(answer)  # Return question and correct answer


def russian_captcha_keyboard(correct_answer):
    """Creates an inline keyboard with possible answers in Russian."""
    markup = types.InlineKeyboardMarkup()
    answers = [correct_answer]  # Include the correct answer
    while len(answers) < 4:  # Generate 3 incorrect options
        incorrect_answer = str(random.randint(int(correct_answer) - 5, int(correct_answer) + 5))  # Generate a number close to the correct answer
        if incorrect_answer not in answers:
            answers.append(incorrect_answer)

    random.shuffle(answers)  # Shuffle the options

    buttons = [types.InlineKeyboardButton(text=answer, callback_data=f"captcha_{answer}") for answer in answers]
    markup.add(*buttons)  # Add all buttons in a single row

    return markup


# END NEW RUSSIAN CAPTCHA


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    referrer_id = None

    if message.text.startswith('/start '):
        try:
            referrer_id = int(message.text.split(' ')[1])
        except ValueError:
            referrer_id = None

    user = get_user(user_id)

    if not user:
        add_user(user_id, username, referrer_id)
        user = get_user(user_id)

    if is_user_banned(user_id):
        bot.send_message(user_id, "Вы заблокированы. хы 🤡")
        return

    # if not user[5]:
    #     question_text, correct_answer = generate_russian_captcha()
    #     sent_message = bot.send_message(user_id, question_text,
    #                                     reply_markup=russian_captcha_keyboard(correct_answer))
    #     set_captcha(sent_message.message_id, correct_answer)  # Store the correct answer
    # else:
    bot.send_message(user_id, "Hello, World! 👋\n\nДобро пожаловать !", reply_markup=main_menu_keyboard())


@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    if user_id in ADMIN_IDS:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = types.KeyboardButton("Просмотр БД 📊")
        item2 = types.KeyboardButton("Забанить пользователя 🚫")
        item3 = types.KeyboardButton("Рассылка сообщения 📢")
        item4 = types.KeyboardButton("Подписка пользователю ✅")
        item5 = types.KeyboardButton("Забрать подписку ❌")
        markup.add(item1, item2, item3, item4, item5)
        bot.send_message(user_id, "Админ-панель 🛡️", reply_markup=markup)
    else:
        bot.send_message(user_id, "шо те тут надо 🤨")


@bot.message_handler(func=lambda message: message.text == "Просмотр БД 📊" and message.from_user.id in ADMIN_IDS)
def view_db(message):
    users = get_all_users()
    text = "Список пользователей:\n"
    for user in users:
        text += f"ID: {user[0]}, Username: @{user[1]}, Дата регистрации: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(user[2]))}, Админ: {user[3]}, Забанен: {user[4]}, Подписка: {user[5]}, Баланс: {user[6]}, Реферер: {user[7]}\n"
    with open("users.txt", "w", encoding="utf-8") as f:
        f.write(text)
    with open("users.txt", "rb") as f:
        bot.send_document(message.chat.id, f)


@bot.message_handler(func=lambda message: message.text == "Забанить пользователя 🚫" and message.from_user.id in ADMIN_IDS)
def ban_user_handler(message):
    bot.send_message(message.chat.id, "Введите @username пользователя для бана:")
    bot.register_next_step_handler(message, process_ban_username)


def process_ban_username(message):
    username = message.text.replace("@", "")
    ban_user(username)
    bot.send_message(message.chat.id, f"Пользователь @{username} забанен.")


@bot.message_handler(func=lambda message: message.text == "Рассылка сообщения 📢" and message.from_user.id in ADMIN_IDS)
def broadcast_message_handler(message):
    bot.send_message(message.chat.id, "Введите сообщение для рассылки:")
    bot.register_next_step_handler(message, process_broadcast_message)


def process_broadcast_message(message):
    broadcast_message = message.text
    send_message_to_all_users(broadcast_message)
    bot.send_message(message.chat.id, "Сообщение отправлено всем пользователям.")


@bot.message_handler(func=lambda message: message.text == "Подписка пользователю ✅" and message.from_user.id in ADMIN_IDS)
def give_subscription_handler(message):
    bot.send_message(message.chat.id, "Введите @username пользователя для выдачи подписки:")
    bot.register_next_step_handler(message, process_give_subscription)


def process_give_subscription(message):
    username = message.text.replace("@", "")
    set_subscription(username, True)
    bot.send_message(message.chat.id, f"Подписка выдана пользователю @{username}.")


@bot.message_handler(func=lambda message: message.text == "Забрать подписку ❌" and message.from_user.id in ADMIN_IDS)
def remove_subscription_handler(message):
    bot.send_message(message.chat.id, "Введите @username пользователя для удаления подписки:")
    bot.register_next_step_handler(message, process_remove_subscription)


def process_remove_subscription(message):
    username = message.text.replace("@", "")
    set_subscription(username, False)
    bot.send_message(message.chat.id, f"Подписка удалена у пользователя @{username}.")


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    user = get_user(user_id)

    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "Вы заблокированы.")
        bot.send_message(user_id, "Вы заблокированы 🤡")
        return

    if call.data.startswith("captcha_"):
        selected_answer = call.data.split("_")[1]
        # No need to regenerate CAPTCHA here, as we'll regenerate it if incorrect

        if selected_answer == get_captcha_answer(call.message.message_id):  # Compare to stored answer
            clear_captcha(call.message.message_id)  # Clear stored captcha

            if not check_subscription(user_id):
                if check_subscription_channel(user_id):
                    set_subscription(user[1], True)
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                            text="Hello, World! 👋\n\nДобро пожаловать !",
                                            reply_markup=main_menu_keyboard())

                    referrer_id = user[7]
                    if referrer_id:
                        if referrer_id != user_id:
                            referrer = get_user(referrer_id)
                            if not already_referred(referrer_id, user_id):
                                increase_referral_balance(referrer_id, REFERRAL_REWARD)
                                add_referral(referrer_id, user_id)
                                new_balance = get_referral_balance(referrer_id)
                                bot.send_message(referrer_id, f"У вас новый реферал! Ваш баланс: {new_balance:.2f}$")
                else:
                    bot.answer_callback_query(call.id, "Необходимо подписаться на канал!")
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                            text="Для доступа к боту необходимо подписаться на канал 🚀",
                                            reply_markup=subscribe_keyboard())
            else:
                bot.answer_callback_query(call.id, "Капча пройдена, но что-то пошло не так.")

        else:
            bot.answer_callback_query(call.id, "Неправильно! Попробуйте еще раз.")
            question_text, correct_answer = generate_russian_captcha()  # Generate new CAPTCHA on incorrect answer
            update_captcha(call.message.message_id, correct_answer)  # Update stored captcha value

            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    text=question_text, reply_markup=russian_captcha_keyboard(correct_answer))

    elif call.data == "telegram_spam":
        user_description = bot.get_chat(user_id).bio if bot.get_chat(user_id).bio else ""
        if "Бесплатный спамер @tg_spamerbot" in user_description:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    text="Введите номер для спам-атаки:\n\nФормат - +79999999999",
                                    reply_markup=back_button_keyboard())
            bot.register_next_step_handler(call.message, process_spam_number)
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    text='Для использования бота добавьте "Бесплатный спамер @tg_spamerbot" в описание своего профиля',
                                    reply_markup=back_button_keyboard())

    elif call.data == "sms_spam":
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                text="coming soon 🛠️", reply_markup=back_button_keyboard())

    elif call.data == "mailer":
        if check_subscription(user_id):
            # Initialize mailer data for user
            mailer_data[user_id] = {}
            sent_msg = bot.send_message(user_id, "Введите количество писем для отправки (1-200):", reply_markup=back_button_keyboard())
            bot.register_next_step_handler(sent_msg, process_mail_count)
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    text="Обратитесь к @new_vanulkin для покупки подписки.",
                                    reply_markup=back_button_keyboard())

    elif call.data == "profile":
        user = get_user(user_id)
        if user:
            reg_date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(user[2]))
            is_admin = "Да" if user[3] == 1 else "Нет"
            profile_text = f"Username: @{user[1]}\nID: {user[0]}\nДата регистрации: {reg_date}\nАдминистратор: {is_admin}"
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    text=profile_text, reply_markup=back_button_keyboard())
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    text="Ошибка получения профиля. 😟", reply_markup=back_button_keyboard())

    elif call.data == "referral_system":
        referral_link = f"t.me/{BOT_USERNAME}?start={user_id}"
        balance = get_referral_balance(user_id)
        text = f"Ваша реферальная ссылка: {referral_link}\nЗа каждого реферала вы получаете {REFERRAL_REWARD:.2f}$\nВаш баланс: {balance:.2f}$"
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text,
                                reply_markup=referral_keyboard())

    elif call.data == "withdraw":
        balance = get_referral_balance(user_id)
        if balance < MIN_WITHDRAWAL:
            bot.answer_callback_query(call.id, f"Вывод доступен от {MIN_WITHDRAWAL:.2f}$")
        else:
            bot.answer_callback_query(call.id, "Заявка на вывод отправлена администраторам.")
            referrals = get_referrals(user_id)
            referral_usernames = []
            for ref_id in referrals:
                ref_user = get_user(ref_id)
                if ref_user:
                    referral_usernames.append(ref_user[1])

            referral_list_text = "\n".join(referral_usernames)

            with open(f"referrals_{user_id}.txt", "w") as f:
                f.write(referral_list_text)

            for admin_id in ADMIN_IDS:
                doc = open(f"referrals_{user_id}.txt", 'rb')
                bot.send_document(admin_id, doc)
                bot.send_message(admin_id, f"Заявка на вывод от @{user[1]}\nБаланс: {balance:.2f}$")
            import os
            os.remove(f"referrals_{user_id}.txt")
    elif call.data == "back_to_menu":
        if user[5]:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    text="Главное меню", reply_markup=main_menu_keyboard())
        else:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    text="Для доступа к боту необходимо подписаться на канал 🚀",
                                    reply_markup=subscribe_keyboard())

    bot.answer_callback_query(call.id)

# spam start
def process_spam_number(message):
    phone = message.text
    try:
        # Validate phone number format using phonenumbers library
        phone_number = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(phone_number):
            bot.send_message(message.chat.id, "Ошибка: Неверный формат номера! ❌")
            return

        bot.delete_message(message.chat.id, message.message_id)
        bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id - 1,
                                text=f"Запущена спам-атака на номер {phone}... 🚀",
                                reply_markup=back_button_keyboard())
        asyncio.run(start_attack(phone, message.chat.id, message.message_id - 1))
        bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id - 1,
                                text=f"Спам-атака на номер {phone} завершена ✅",
                                reply_markup=back_button_keyboard())
    except phonenumbers.phonenumberutil.NumberParseException:
        bot.send_message(message.chat.id, "Ошибка: Неверный формат номера! ❌")
    except Exception as e:
        print(e)

# Refactored send_request function
async def send_request(url, phone, session):
    try:
        user_agent = random.choice(spam.user_agents)
        headers = {
            'User-Agent': user_agent,
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        # Retry mechanism with exponential backoff
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                async with session.post(url, headers=headers, data=f'phone={phone}', ssl=False,
                                        timeout=10) as response:  # Added timeout and ssl=False
                    if response.status == 200:
                        return {
                            'success': True,
                            'status': response.status,
                            'url': url,
                            'hostname': url.split('//')[-1].split('/')[0] if '//' in url else url.split('/')[0],
                            'user_agent': user_agent,
                        }
                    else:
                        print(f"Attempt {attempt + 1} failed with status {response.status} for {url}")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                #raise Exception(f"Request failed with status {response.status}") # Remove the try-except
            except asyncio.TimeoutError:
                print(f"Timeout on attempt {attempt + 1} for {url}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            except aiohttp.ClientError as e:  # More specific exception
                print(f"ClientError on attempt {attempt + 1} for {url}: {e}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2


        return {'error': 'Max retries exceeded',
                'hostname': url.split('//')[-1].split('/')[0] if '//' in url else url.split('/')[0],
                'user_agent': user_agent}

    except Exception as e:  # Catch general exceptions
        print(f"General exception for {url}: {e}")
        return {'error': str(e),
                'hostname': url.split('//')[-1].split('/')[0] if '//' in url else url.split('/')[0],
                'user_agent': user_agent}


async def start_attack(phone, chat_id, message_id):
    # Validate phone number using phonenumbers library
    try:
        phone_number = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(phone_number):
            bot.send_message(chat_id, "Ошибка: Неверный формат номера! ❌")
            return
    except phonenumbers.phonenumberutil.NumberParseException:
        bot.send_message(chat_id, "Ошибка: Неверный формат номера! ❌")
        return

    success_count = 0
    error_count = 0
    warning_count = 0

    ua = random.choice(spam.user_agents)

    async with aiohttp.ClientSession() as session:
        tasks = [send_request(url, phone, session) for url in spam.URLs]
        results = await asyncio.gather(*tasks)

        for result in results:
            if 'error' in result:
                bot.send_message(chat_id,
                                 f"Ошибка: {result['error']} - {result['hostname']} (User-Agent: {result['user_agent']}) ⚠️")
                error_count += 1
            elif result['success']:
                success_count += 1
                # bot.send_message(chat_id, f"Успех: {result['hostname']} ✅") # To avoid flood - removed messages
            else:
                warning_count += 1
                bot.send_message(chat_id,
                                 f"Предупреждение: {result['status']} - {result['hostname']} (User-Agent: {result['user_agent']}) ❗")  # To avoid flood - removed messages

    bot.send_message(chat_id,
                     f"Атака завершена!\nУспешных запросов: {success_count} ✅\nОшибок: {error_count} ⚠️\nПредупреждений: {warning_count} ❗")


def process_mail_count(message):
    user_id = message.from_user.id
    try:
        count = int(message.text)
        if 1 <= count <= 200:
            bot.delete_message(message.chat.id, message.message_id)
            mailer_data[user_id]['count'] = count
            sent_msg = bot.send_message(user_id, "Введите почту для отправки писем:", reply_markup=back_button_keyboard())
            bot.register_next_step_handler(sent_msg, process_mail_address)
        else:
            bot.send_message(message.chat.id, "Неверное количество писем (1-200).")
    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат числа.")

def process_mail_address(message):
    user_id = message.from_user.id
    email_address = message.text
    if "@" not in email_address:
        bot.send_message(message.chat.id, "Неверный формат почты.")
        return

    bot.delete_message(message.chat.id, message.message_id)
    mailer_data[user_id]['email_address'] = email_address
    sent_msg = bot.send_message(user_id, "Введите тему письма:", reply_markup=back_button_keyboard())
    bot.register_next_step_handler(sent_msg, process_mail_subject)

def process_mail_subject(message):
    user_id = message.from_user.id
    subject = message.text
    bot.delete_message(message.chat.id, message.message_id)
    mailer_data[user_id]['subject'] = subject
    sent_msg = bot.send_message(user_id, "Введите содержание письма:", reply_markup=back_button_keyboard())
    bot.register_next_step_handler(sent_msg, process_mail_content)

def process_mail_content(message):
    user_id = message.from_user.id
    content = message.text
    bot.delete_message(message.chat.id, message.message_id)
    mailer_data[user_id]['content'] = content
    bot.send_message(user_id, "Начинаю рассылку писем...", reply_markup=back_button_keyboard())
    send_emails(user_id)


def send_emails(user_id):
    try:
        count = mailer_data[user_id]['count']
        to_email = mailer_data[user_id]['email_address']
        subject = mailer_data[user_id]['subject']
        content = mailer_data[user_id]['content']
        chat_id = bot.get_chat(user_id).id

        with open(MAIL_FILE, "r") as f:
            mail_data = [line.strip().split(":") for line in f]

        for i in range(count):
            from_email, password = random.choice(mail_data)
            msg = MIMEText(content)
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = to_email

            with smtplib.SMTP('smtp.firstmail.ru', 587) as server:
                server.starttls()
                server.login(from_email, password)
                server.sendmail(from_email, to_email, msg.as_string())

        bot.send_message(chat_id, "Рассылка писем завершена!", reply_markup=back_button_keyboard())
    except FileNotFoundError:
        bot.send_message(chat_id, "Файл mail.txt не найден.")
    except KeyError:
        bot.send_message(chat_id, "Данные для рассылки не найдены. Пожалуйста, начните заново.")
    except Exception as e:
        print(e)
        bot.send_message(chat_id, f"Произошла ошибка при отправке писем: {e}")
    finally:
        # Clean up mailer data after attempt
        if user_id in mailer_data:
            del mailer_data[user_id]

def check_subscription_channel(user_id):
    try:
        chat_member = bot.get_chat_member(CHANNEL_ID, user_id)
        return chat_member.status in ['member', 'administrator', 'creator', 'restricted']
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False

def already_referred(referrer_id, user_id):
    cursor.execute("SELECT * FROM referrals WHERE referrer_id = ? AND referral_id = ?", (referrer_id, user_id))
    return cursor.fetchone() is not None

if __name__ == '__main__':
    try:
        import spam
    except Exception as e:
        print(e)
        print('Please install spam')

    bot.infinity_polling()
