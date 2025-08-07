
import telebot
from telebot import types
import sqlite3

# Замените 'YOUR_BOT_TOKEN' на токен вашего бота
BOT_TOKEN = '8333530464:AAEB6PxDR2Obyxdez8Tm5xD3w_U4sexjUoI'

bot = telebot.TeleBot(BOT_TOKEN)

# Подключение к базе данных SQLite
DATABASE_NAME = 'channel_data.db'

def create_connection():
    """Создает соединение с базой данных SQLite."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        return conn
    except sqlite3.Error as e:
        print(f"Ошибка при подключении к базе данных: {e}")
    return conn

def create_table():
    """Создает таблицу для хранения данных о каналах."""
    conn = create_connection()
    if conn is not None:
        try:
            sql = """
            CREATE TABLE IF NOT EXISTS channels (
                user_chat_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                text_to_add TEXT
            );
            """
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            print("Таблица channels создана успешно")
        except sqlite3.Error as e:
            print(f"Ошибка при создании таблицы: {e}")
        finally:
            conn.close()

create_table()  # Создаем таблицу при запуске бота

# Markdown разметка
markdown_help = """
*Markdown разметка:*

_Курсив_: `_текст_` или `*текст*`
*Жирный*: `**текст**` или `__текст__`
`Моноширинный текст`: ``текст``
[Ссылка](https://www.example.com)
"""

# --- Обработчики ---

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start."""
    bot.send_message(message.chat.id, "Привет! Для начала работы, добавьте меня в канал, сделайте администратором и перешлите любое сообщение из канала мне.")

@bot.message_handler(func=lambda message: message.forward_from_chat is not None, content_types=['text', 'photo', 'video', 'audio', 'document'])
def handle_forwarded_message(message):
    """Обработчик пересланных сообщений из канала."""
    chat_id = message.chat.id
    forwarded_from_chat = message.forward_from_chat

    # Проверяем, является ли бот администратором в канале
    try:
        chat_member = bot.get_chat_member(forwarded_from_chat.id, bot.get_me().id)
        if chat_member.status in ['administrator', 'creator']:
            # Если бот администратор, сохраняем ID канала и запрашиваем текст
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM channels WHERE user_chat_id=?", (chat_id,))
            existing_data = cursor.fetchone()
            if existing_data:
                sql = "UPDATE channels SET channel_id=? WHERE user_chat_id=?"
                cursor.execute(sql, (forwarded_from_chat.id, chat_id))

            else:
                sql = "INSERT INTO channels (user_chat_id, channel_id, text_to_add) VALUES (?, ?, ?)"
                cursor.execute(sql, (chat_id, forwarded_from_chat.id, None))  # Изначально текст_to_add = None

            conn.commit()
            conn.close()


            bot.send_message(chat_id, "Отлично! Я являюсь администратором в канале. Теперь введите текст, который будет добавляться к каждому посту (можно использовать Markdown):")
            bot.register_next_step_handler(message, get_text_to_add)
        else:
            bot.send_message(chat_id, "Я не администратор в этом канале. Пожалуйста, сделайте меня администратором и повторите попытку.")

    except telebot.apihelper.ApiTelegramException as e:
        if e.description == 'Forbidden: bot was kicked from the group chat':
            bot.send_message(chat_id, "Меня заблокировали в этом канале. Пожалуйста, добавьте меня снова и сделайте администратором.")
        elif e.description == 'Forbidden: bot is not a member of the group chat':
            bot.send_message(chat_id, "Я не состою в этом канале. Пожалуйста, добавьте меня и сделайте администратором.")
        else:
            bot.send_message(chat_id, f"Произошла ошибка при проверке прав: {e}")


def get_text_to_add(message):
    """Получает текст, который нужно добавлять к постам."""
    chat_id = message.chat.id
    text_to_add = message.text

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM channels WHERE user_chat_id=?", (chat_id,))
    result = cursor.fetchone()
    channel_id = result[0]
    conn.close()

    chat_info = bot.get_chat(channel_id)
    channel_title = chat_info.title if chat_info.title else "Название канала не найдено"


    conn = create_connection()
    cursor = conn.cursor()
    sql = "UPDATE channels SET text_to_add=? WHERE user_chat_id=?"
    cursor.execute(sql, (text_to_add, chat_id))
    conn.commit()
    conn.close()


    # Создаем inline-кнопки
    markup = types.InlineKeyboardMarkup(row_width=2)
    item_confirm = types.InlineKeyboardButton("Подтвердить", callback_data='confirm')
    item_cancel = types.InlineKeyboardButton("Отмена", callback_data='cancel')
    markup.add(item_confirm, item_cancel)

    bot.send_message(chat_id, f"Название канала: [{channel_title}]\nЖелаемый текст: [{text_to_add}]\n\nПодтвердить?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    """Обработчик inline-кнопок."""
    chat_id = call.message.chat.id
    if call.data == "confirm":
        # Подтверждаем добавление текста
        bot.answer_callback_query(call.id, "Подтверждено! Теперь я буду добавлять текст к постам в канале.")
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="Настройки сохранены! Теперь я буду добавлять текст к постам в канале.")
    elif call.data == "cancel":
        # Отменяем добавление текста
        bot.answer_callback_query(call.id, "Отменено.")
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="Действие отменено.")
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE channels SET text_to_add=? WHERE user_chat_id=?", (None, chat_id))
        conn.commit()
        conn.close()

    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)


@bot.message_handler(commands=['help_markdown'])
def help_markdown(message):
    """Отправляет подсказку по Markdown разметке."""
    bot.send_message(message.chat.id, markdown_help, parse_mode="Markdown")


# --- Обработчик для изменения постов в канале ---
@bot.channel_post_handler(func=lambda message: True)
def handle_channel_post(message):
    """Обработчик новых постов в канале."""
    chat_id = message.chat.id

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_chat_id, text_to_add FROM channels WHERE channel_id=?", (chat_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        user_chat_id = result[0]
        text_to_add = result[1]

        if text_to_add:
            try:
                # Добавляем текст к посту
                new_text = message.text if message.text else message.caption
                if new_text:
                    new_text += "\n\n" + text_to_add

                # Отправляем отредактированное сообщение
                if message.text:
                    bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=new_text, parse_mode="Markdown")
                elif message.caption:
                    bot.edit_message_caption(chat_id=chat_id, message_id=message.message_id, caption=new_text, parse_mode="Markdown")
            except telebot.apihelper.ApiTelegramException as e:
                print(f"Ошибка при редактировании сообщения: {e}")


# Запуск бота
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
