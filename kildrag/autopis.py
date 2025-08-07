from telethon import TelegramClient, events

# Замените на свои значения
api_id = 24817168  # Получите api_id с сайта my.telegram.org
api_hash = 'ffca85e599c73cae5773019de5fc8804'  # Получите api_hash с сайта my.telegram.org
phone_number = '+79088103080'  # Ваш номер телефона

# ID канала и чата
channel_id = -1001711497553
chat_id = -1002800233397

# Сообщение для ответа
response_message = "Это заранее заготовленное сообщение от userbot!"

# Создаем клиент
client = TelegramClient('userbot', api_id, api_hash)

# Функция для обработки нового сообщения в чате
@client.on(events.NewMessage(chats=chat_id))
async def handler(event):
    message = event.message

    # Проверяем, что сообщение пришло из указанного канала
    if message.sender_id == channel_id:
        print(f"Обнаружено сообщение от канала {channel_id} в чате {chat_id}")

        # Отвечаем на сообщение канала
        await client.send_message(chat_id, response_message, reply_to=message)
        print(f"Отвечено на сообщение от канала {channel_id}")

# Функция для запуска клиента и получения кода авторизации (при необходимости)
async def main():
    await client.start(phone=phone_number)  # Добавьте phone=phone_number

    # Если вы запускаете скрипт впервые, вам будет предложено ввести код авторизации
    # из Telegram.  Сохраните сессию, и в будущем код вводить не потребуется.
    print("Userbot запущен. Ожидание сообщений...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
