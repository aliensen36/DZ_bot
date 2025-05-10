import logging

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from database.requests import UserRequests


logger = logging.getLogger(__name__)

start_router = Router()


# ----- ОБРАБОТКА /start -----------
@start_router.message(CommandStart())
async def cmd_start(message: Message):
    user = await UserRequests.get_or_create_from_telegram(message.from_user)
    await message.answer(f"✨ Привет, <b>{user.first_name}</b>! ✨\n\n"
                         f"Рады тебя видеть в нашем боте! 🤖💫")

