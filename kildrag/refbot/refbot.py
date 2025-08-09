
import telebot
import sqlite3
import time
import random
from telebot import types

# --- Настройки ---
TOKEN = "8297879729:AAFamUsCgP8M2VEDYlOy8pKYxnO8i99qvyk"  # Замените на токен вашего бота
ADMIN_IDS = ["7163004463", "7465411120"]  # Замените на ID администраторов (можно несколько)
CHANNEL_IDS = ["-1002530726106", "-1002421952894"]  # Замените на ID каналов для подписки
CHANNEL_LINKS = ["https://t.me/+XFo1yTBtmjcyYTRi", "https://t.me/+aBuvDmeMWmtiZGEy"]  # Замените на ссылки на каналы для подписки
BOT_USERNAME = "reff_tgbot"  # Замените на username вашего бота

# --- База данных ---
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0.0,
        referrals INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        last_click REAL DEFAULT 0.0,
        referred_by INTEGER DEFAULT 0
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS bot_info (
        start_time REAL
    )
""")

cursor.execute("SELECT start_time FROM bot_info")
start_time = cursor.fetchone()
if start_time is None:
    cursor.execute("INSERT INTO bot_info (start_time) VALUES (?)", (time.time(),))

conn.commit()

# --- Инициализация бота ---
bot = telebot.TeleBot(TOKEN)

# --- Хранение информации о капче ---
captcha_data = {}


# --- Функции для работы с базой данных ---
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cursor.fetchone()


def create_user(user_id, username):
    cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()


def update_balance(user_id, amount):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()


def get_balance(user_id):
    user = get_user(user_id)
    return user[2] if user else 0.0


def increment_clicks(user_id):
    cursor.execute("UPDATE users SET clicks = clicks + 1 WHERE user_id = ?", (user_id,))
    conn.commit()


def update_last_click(user_id):
    cursor.execute("UPDATE users SET last_click = ? WHERE user_id = ?", (time.time(), user_id))
    conn.commit()


def get_last_click(user_id):
    user = get_user(user_id)
    return user[5] if user else 0.0


def add_referral(referrer_id):
    cursor.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
    conn.commit()


def get_referrals(user_id):
    user = get_user(user_id)
    return user[3] if user else 0


def reset_balance(user_id):
    cursor.execute("UPDATE users SET balance = 0.0 WHERE user_id = ?", (user_id,))
    conn.commit()


def is_user_registered(user_id):
    return get_user(user_id) is not None


def set_referred_by(user_id, referrer_id):
    cursor.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referrer_id, user_id))
    conn.commit()


def get_referred_by(user_id):
    cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0


# --- Проверка подписки на каналы ---
def check_subscription(user_id):
    for channel_id in CHANNEL_IDS:
        try:
            member = bot.get_chat_member(channel_id, user_id)
            if member.status in ['left', 'kicked', 'banned']:
                return False
        except Exception as e:
            print(f"Ошибка при проверке подписки: {e}")  # Добавьте обработку ошибок
            return False
    return True


# --- Генерация капчи ---
def generate_captcha():
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    operation = random.choice(['+', '-'])
    if operation == '+':
        answer = num1 + num2
        question = f"{num1} + {num2} = ?"
    else:
        answer = num1 - num2
        question = f"{num1} - {num2} = ?"
    return question, answer


# --- Обработчики команд ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username

    if not is_user_registered(user_id):
        create_user(user_id, username)

    referred_by_id = None
    if message.text.startswith('/start '):
        try:
            referred_by_id = int(message.text.split()[1])
            if referred_by_id == user_id:
                bot.reply_to(message, "Нельзя быть рефералом самого себя!")
                referred_by_id = None  # Сбросить, чтобы не засчитался как реферал
            elif is_user_registered(user_id):
                bot.reply_to(message, "Вы уже зарегистрированы в боте!")
                referred_by_id = None
        except ValueError:
            bot.reply_to(message, "Неверный формат реферальной ссылки.")
            referred_by_id = None

    if not check_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        for i, channel_link in enumerate(CHANNEL_LINKS):
            markup.add(types.InlineKeyboardButton(text=f"Подписаться на канал {i+1}", url=channel_link))
        bot.send_message(user_id, "Для продолжения использования бота, подпишитесь на каналы:", reply_markup=markup)
    else:
        if referred_by_id:
            if get_referred_by(user_id) == 0:  # Проверить, что пользователь еще не был рефералом
                add_referral(referred_by_id)
                update_balance(referred_by_id, 0.03)
                set_referred_by(user_id, referred_by_id)  # Записать, кто пригласил пользователя
                bot.send_message(referred_by_id, f"Новый реферал по вашей ссылке! +0.03$")
            else:
                bot.reply_to(message, "Вы уже являетесь чьим-то рефералом.")

        send_main_menu(message)


def send_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item1 = types.KeyboardButton("Клик")
    item2 = types.KeyboardButton("Реф система")
    item3 = types.KeyboardButton("Профиль")
    item4 = types.KeyboardButton("Информация")
    markup.add(item1, item2, item3, item4)
    bot.send_message(message.chat.id, "Добро пожаловать в главное меню!", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Клик")
def click(message):
    user_id = message.from_user.id
    last_click = get_last_click(user_id)
    time_diff = time.time() - last_click

    if user_id in captcha_data and not captcha_data[user_id]['solved']:
        bot.reply_to(message, "Пожалуйста, решите капчу для продолжения кликов.")
        return

    user_data = get_user(user_id)
    if user_data:
        clicks = user_data[4]

        if clicks > 0 and clicks % 20 == 0:
            question, answer = generate_captcha()
            captcha_data[user_id] = {'answer': answer, 'solved': False}
            bot.send_message(user_id, f"Для продолжения кликов, решите капчу:\n{question}")
            return

    if time_diff < 0.5:
        wait_time = 0.5 - time_diff
        bot.reply_to(message, f"Подождите {wait_time:.1f} секунд до следующего клика.")
    else:
        update_balance(user_id, 0.005)
        increment_clicks(user_id)
        update_last_click(user_id)
        bot.reply_to(message, "+0.005$ на баланс!")


@bot.message_handler(func=lambda message: message.text == "Реф система")
def ref_system(message):
    user_id = message.from_user.id
    ref_link = f"t.me/{BOT_USERNAME}?start={user_id}"
    referrals = get_referrals(user_id)
    balance = get_balance(user_id)

    text = f"Ваша реферальная ссылка: {ref_link}\n" \
           f"За каждого реферала вы получаете 0.03$ (только если реферал подписался на каналы).\n" \
           f"У вас {referrals} рефералов.\n" \
           f"Ваш реферальный баланс: {referrals * 0.03:.2f}$"

    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda message: message.text == "Профиль")
def profile(message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if user:
        username = user[1]
        balance = user[2]
        clicks = user[4]
        referrals = user[3]

        text = f"Ваш профиль:\n" \
               f"Username: @{username}\n" \
               f"ID: {user_id}\n" \
               f"Баланс: {balance:.2f}$\n" \
               f"Кликов: {clicks}\n" \
               f"Рефералов: {referrals}"

        markup = types.InlineKeyboardMarkup()
        item_withdraw = types.InlineKeyboardButton("Вывести", callback_data='withdraw')
        markup.add(item_withdraw)

        bot.send_message(message.chat.id, text, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Произошла ошибка. Попробуйте перезапустить бота командой /start")


@bot.message_handler(func=lambda message: message.text == "Информация")
def info(message):
    cursor.execute("SELECT start_time FROM bot_info")
    start_time = cursor.fetchone()[0]
    uptime = time.time() - start_time

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # Рассчитайте общую сумму выведенных средств (это сложнее без отдельной таблицы выводов)
    # Предположим, что все с нулевым балансом - вывели все деньги
    cursor.execute("SELECT SUM(balance) FROM users")
    total_balance = cursor.fetchone()[0]
    total_withdrawals = 0  # Невозможно точно определить без отдельной таблицы выводов

    text = f"Информация о боте:\n" \
           f"Первый запуск: {time.ctime(start_time)}\n" \
           f"Всего пользователей: {total_users}\n" \
           f"Всего выведено: {total_withdrawals:.2f}$ (приблизительно)"

    markup = types.InlineKeyboardMarkup()
    item_coder = types.InlineKeyboardButton("Кодер", url="t.me/new_vanulkin")
    item_owner = types.InlineKeyboardButton("Владелец", url="t.me/drag_kil")
    markup.add(item_coder, item_owner)

    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    if str(user_id) in ADMIN_IDS:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        item1 = types.KeyboardButton("Просмотр БД")
        item2 = types.KeyboardButton("Выдать бан")
        item3 = types.KeyboardButton("Разбанить")
        item4 = types.KeyboardButton("Выдать баланс")
        item5 = types.KeyboardButton("Забрать баланс")
        markup.add(item1, item2, item3, item4, item5)
        bot.send_message(message.chat.id, "Добро пожаловать в админ-панель!", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этой команде.")


@bot.message_handler(func=lambda message: message.text == "Просмотр БД")
def view_db(message):
    user_id = message.from_user.id
    if str(user_id) in ADMIN_IDS:
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        text = "Список пользователей:\n"
        for user in users:
            text += f"ID: {user[0]}, Username: @{user[1]}, Баланс: {user[2]}, Рефералы: {user[3]}, Клики: {user[4]}\n"
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этой функции.")


@bot.message_handler(func=lambda message: message.text == "Выдать бан")
def ban_user(message):
    user_id = message.from_user.id
    if str(user_id) in ADMIN_IDS:
        bot.send_message(message.chat.id, "Введите ID или @username пользователя, которого нужно забанить:")
        bot.register_next_step_handler(message, process_ban)
    else:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этой функции.")


def process_ban(message):
    try:
        user_id = int(message.text)
        # Здесь нужно добавить код для бана пользователя (например, добавить его в отдельную таблицу забаненных)
        bot.send_message(message.chat.id, f"Пользователь с ID {user_id} забанен.")
    except ValueError:
        username = message.text
        # Здесь нужно добавить код для поиска пользователя по username и его бана
        bot.send_message(message.chat.id, f"Пользователь с username {username} забанен.")
    # TODO: Реализовать логику бана


@bot.message_handler(func=lambda message: message.text == "Разбанить")
def unban_user(message):
    user_id = message.from_user.id
    if str(user_id) in ADMIN_IDS:
        bot.send_message(message.chat.id, "Введите ID или @username пользователя, которого нужно разбанить:")
        bot.register_next_step_handler(message, process_unban)
    else:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этой функции.")


def process_unban(message):
    try:
        user_id = int(message.text)
        # Здесь нужно добавить код для разбана пользователя (например, удалить его из таблицы забаненных)
        bot.send_message(message.chat.id, f"Пользователь с ID {user_id} разбанен.")
    except ValueError:
        username = message.text
        # Здесь нужно добавить код для поиска пользователя по username и его разбана
        bot.send_message(message.chat.id, f"Пользователь с username {username} разбанен.")
    # TODO: Реализовать логику разбана


@bot.message_handler(func=lambda message: message.text == "Выдать баланс")
def give_balance(message):
    user_id = message.from_user.id
    if str(user_id) in ADMIN_IDS:
        bot.send_message(message.chat.id, "Введите ID или @username пользователя, которому нужно выдать баланс:")
        bot.register_next_step_handler(message, process_give_balance_user)
    else:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этой функции.")


def process_give_balance_user(message):
    try:
        target = int(message.text)
        bot.send_message(message.chat.id, "Теперь введите сумму, которую нужно выдать:")
        bot.register_next_step_handler(message, lambda msg: process_give_balance_amount(msg, target))
    except ValueError:
        target = message.text
        bot.send_message(message.chat.id, "Теперь введите сумму, которую нужно выдать:")
        bot.register_next_step_handler(message, lambda msg: process_give_balance_amount(msg, target))


def process_give_balance_amount(message, target):
    try:
        amount = float(message.text)
        if isinstance(target, int):
            update_balance(target, amount)
            bot.send_message(message.chat.id, f"{amount}$ успешно выдано пользователю с ID {target}.")
        else:
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (target,))
            user = cursor.fetchone()
            if user:
                update_balance(user[0], amount)
                bot.send_message(message.chat.id, f"{amount}$ успешно выдано пользователю с username {target}.")
            else:
                bot.send_message(message.chat.id, "Пользователь не найден.")
    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат суммы.")


@bot.message_handler(func=lambda message: message.text == "Забрать баланс")
def take_balance(message):
    user_id = message.from_user.id
    if str(user_id) in ADMIN_IDS:
        bot.send_message(message.chat.id, "Введите ID или @username пользователя, у которого нужно забрать баланс:")
        bot.register_next_step_handler(message, process_take_balance_user)
    else:
        bot.send_message(message.chat.id, "У вас нет прав для доступа к этой функции.")


def process_take_balance_user(message):
    try:
        target = int(message.text)
        bot.send_message(message.chat.id, "Теперь введите сумму, которую нужно забрать:")
        bot.register_next_step_handler(message, lambda msg: process_take_balance_amount(msg, target))
    except ValueError:
        target = message.text
        bot.send_message(message.chat.id, "Теперь введите сумму, которую нужно забрать:")
        bot.register_next_step_handler(message, lambda msg: process_take_balance_amount(msg, target))


def process_take_balance_amount(message, target):
    try:
        amount = float(message.text)
        amount = -amount  # Make amount negative to subtract
        if isinstance(target, int):
            update_balance(target, amount)
            bot.send_message(message.chat.id, f"{amount}$ успешно забрано у пользователя с ID {target}.")
        else:
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (target,))
            user = cursor.fetchone()
            if user:
                update_balance(user[0], amount)
                bot.send_message(message.chat.id, f"{amount}$ успешно забрано у пользователя с username {target}.")
            else:
                bot.send_message(message.chat.id, "Пользователь не найден.")
    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат суммы.")


# --- Обработчики callback запросов ---
@bot.callback_query_handler(func=lambda call: call.data == 'withdraw')
def withdraw(call):
    user_id = call.from_user.id
    username = call.from_user.username
    balance = get_balance(user_id)

    if balance < 1.0:
        bot.answer_callback_query(call.id, "Вывод доступен от 1$.")
    else:
        reset_balance(user_id)
        bot.answer_callback_query(call.id, "Заявка на вывод отправлена.")

        admin_message = f"Заявка на вывод:\nUsername: @{username}\nID: {user_id}\nСумма: {balance:.2f}$"
        markup = types.InlineKeyboardMarkup()
        item_paid = types.InlineKeyboardButton("Вывели", callback_data=f"paid_{user_id}")
        markup.add(item_paid)

        for admin_id in ADMIN_IDS:
            message = bot.send_message(admin_id, admin_message, reply_markup=markup)
            bot.pin_chat_message(admin_id, message.message_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('paid_'))
def paid(call):
    user_id = call.data.split('_')[1]
    user_id = int(user_id)  # Convert user_id to integer
    bot.send_message(user_id, "Вывод был успешно осуществлен.")
    bot.answer_callback_query(call.id, "Пользователь уведомлен.")
    for admin_id in ADMIN_IDS:
        try:
            bot.unpin_chat_message(admin_id, call.message.message_id)  # Unpin the message in admin chats
        except Exception as e:
            print(f"Ошибка при откреплении сообщения: {e}")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    if user_id in captcha_data and not captcha_data[user_id]['solved']:
        try:
            answer = int(message.text)
            if answer == captcha_data[user_id]['answer']:
                captcha_data[user_id]['solved'] = True
                bot.reply_to(message, "Капча решена! Теперь вы можете продолжить клики.")
            else:
                bot.reply_to(message, "Неверный ответ. Попробуйте еще раз.")
        except ValueError:
            bot.reply_to(message, "Пожалуйста, введите числовой ответ.")


# --- Запуск бота ---
if __name__ == '__main__':
    print("Бот запущен...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Бот упал с ошибкой: {e}")
        time.sleep(15)
