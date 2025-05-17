import logging
import aiohttp
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from data.url import url_users
from keyboards.reply import main_kb

logger = logging.getLogger(__name__)

start_router = Router()


@start_router.message(CommandStart())
async def cmd_start(message: Message):
    user_data = {
        "tg_id": message.from_user.id,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "username": message.from_user.username,
        "is_bot": message.from_user.is_bot,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url_users, json=user_data) as resp:
            data = await resp.json()

    await message.answer(f"✨ Привет, <b>{data['first_name']}</b>! ✨\n\n"
                         f"Рады тебя видеть в нашем боте! 🤖💫",
                         reply_markup=main_kb)

