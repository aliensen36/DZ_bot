import aiohttp
import io


# Функция для загрузки фото из Telegram
async def download_photo_from_telegram(bot, file_id: str) -> io.BytesIO:
    file = await bot.get_file(file_id)
    file_path = file.file_path
    telegram_file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_path}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(telegram_file_url) as resp:
            if resp.status == 200:
                file_content = await resp.read()
                return io.BytesIO(file_content)
            else:
                raise Exception(f"Не удалось загрузить файл из Telegram: {resp.status}")
    