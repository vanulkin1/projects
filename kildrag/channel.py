import telebot
from telebot import types

# Замените '8353371171:AAGWtgSPAxF3ii_BGrOfyVb-C7hmb6oKaFc' на токен вашего бота
TOKEN = '8353371171:AAGWtgSPAxF3ii_BGrOfyVb-C7hmb6oKaFc'
# Замените '-1002530726106' на ID вашего канала
CHANNEL_ID = -1002530726106
# Замените 'Название вашего канала' на название вашего канала
CHANNEL_NAME = 'KIL DRAG| SKAM LIST'

bot = telebot.TeleBot(TOKEN)


@bot.chat_join_request_handler()
def handle_join_request(join_request: telebot.types.ChatJoinRequest):
    """Обрабатывает запрос на вступление в канал."""

    user_id = join_request.from_user.id
    chat_id = join_request.chat.id

    # Проверяем, что запрос именно в наш канал
    if chat_id == CHANNEL_ID:
        # Отправляем пользователю сообщение с капчей
        markup = types.InlineKeyboardMarkup(row_width=1)
        itembtn = types.InlineKeyboardButton("Я не робот", callback_data=f"captcha_{user_id}")
        markup.add(itembtn)

        try:
            bot.send_message(
                user_id,
                f"Чтобы вступить в канал {CHANNEL_NAME}, пожалуйста, пройдите капчу:",
                reply_markup=markup
            )
        except telebot.apihelper.ApiTelegramException as e:
            if e.result_json['description'] == "Forbidden: bot can't initiate conversation with a user":
                print(f"Невозможно отправить сообщение пользователю {user_id}.  Бот заблокирован пользователем или пользователь не начинал разговор с ботом.")
                # В этом месте можно добавить логику отклонения заявки, если бот не может связаться с пользователем.
                # bot.decline_chat_join_request(chat_id=CHANNEL_ID, user_id=user_id)
            else:
                print(f"Другая ошибка при отправке сообщения: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("captcha_"))
def callback_inline(call):
    """Обрабатывает нажатие на кнопку "Я не робот"."""
    try:
        user_id = int(call.data.split("_")[1])

        # Принимаем запрос на вступление в канал
        bot.approve_chat_join_request(chat_id=CHANNEL_ID, user_id=user_id)

        # Отправляем пользователю подтверждение
        try:
             bot.send_message(user_id, f"Добро пожаловать в канал {CHANNEL_NAME}!")
        except telebot.apihelper.ApiTelegramException as e:
             if e.result_json['description'] == "Forbidden: bot can't initiate conversation with a user":
                 print(f"Невозможно отправить сообщение пользователю {user_id} о принятии в канал.  Бот заблокирован пользователем или пользователь не начинал разговор с ботом.")
             else:
                 print(f"Другая ошибка при отправке сообщения: {e}")

        #Удаляем сообщение с капчей
        bot.delete_message(call.message.chat.id, call.message.message_id)

    except Exception as e:
        print(f"Ошибка при обработке капчи: {e}")
        try:
            bot.send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте позже.")
        except telebot.apihelper.ApiTelegramException as e:
            if e.result_json['description'] == "Forbidden: bot can't initiate conversation with a user":
                print(f"Невозможно отправить сообщение об ошибке пользователю {call.message.chat.id}. Бот заблокирован пользователем или пользователь не начинал разговор с ботом.")
            else:
                print(f"Другая ошибка при отправке сообщения: {e}")


if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
