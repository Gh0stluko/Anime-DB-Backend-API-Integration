import asyncio
from telegram import Bot

# Замініть 'YOUR_TELEGRAM_BOT_TOKEN' на токен вашого бота
TOKEN = '7430570719:AAGVdpU5-EeKz2GL_I6rDbeKu5RRuaQjB-s'
bot = Bot(token=TOKEN)

async def main():
    # Отримуємо оновлення (updates) асинхронно
    updates = await bot.get_updates()
    print("Кількість оновлень:", len(updates))
    for update in updates:
        message = update.message
        print("Повідомлення:", message)
        if message:
            if message.video:
                file_id = message.video.file_id
                # Отримуємо об'єкт File асинхронно за допомогою bot.get_file
                file_obj = await bot.get_file(file_id)
                # Формуємо URL до файлу
                video_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_obj.file_path}"
                print("URL відео:", video_url)
            else:
                print("В повідомленні немає відео.")

if __name__ == '__main__':
    asyncio.run(main())
