import aiohttp
import io
from aiogram.types import Message
from aiogram.types import ContentType

from .constants import MAX_PHOTO_SIZE


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

# Проверяет, является ли сообщение фото, и соответствует ли оно требованиям (формат JPG/PNG, размер до 10MB)
async def validate_photo(message: Message) -> tuple[bool, str]:
    if message.content_type != ContentType.PHOTO:
        return False, "Пожалуйста, отправьте изображение в формате JPG или PNG."
    if not message.photo:
        return False, "Фото не получено. Пожалуйста, отправьте изображение."
    photo = message.photo[-1]
    if photo.file_size > MAX_PHOTO_SIZE:
        return False, "Фото слишком большое. Максимальный размер: 10 МБ."
    return True, photo.file_id