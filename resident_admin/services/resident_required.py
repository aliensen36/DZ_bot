from functools import wraps
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import aiohttp

from data.config import config_settings
from data.url import url_resident


def resident_required(func):
    @wraps(func)
    async def wrapper(message: Message, state: FSMContext, *args, **kwargs):
        data = await state.get_data()
        resident_id = data.get('resident_id')
        if not resident_id:
            await message.answer("Сначала войдите в резидентскую админ-панель командой /res_admin")
            return

        # Проверка, что имя резидента уже есть в state (значит, сообщение уже выводилось)
        resident_name = data.get('resident_name')
        if not resident_name:
            # Получаем имя резидента из API
            headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            url = f"{url_resident}{resident_id}/"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        resident_data = await response.json()
                        resident_name = resident_data.get("name")
                        # Сохраняем имя в state
                        await state.update_data(resident_name=resident_name)
                    else:
                        await message.answer(f"Резидент с ID {resident_id} не найден.")
                        return

        # НЕ отправляем сообщение снова
        return await func(message, state, *args, **kwargs)
    return wrapper
