import logging

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from database.requests import create_user

import keyboards.keyboards as kb


logger = logging.getLogger(__name__)

user = Router()


# ----- ОБРАБОТКА /start -----------
@user.message(CommandStart())
async def cmd_start(message: Message):
    await create_user(message.from_user.id)
    await message.answer(
        "Добро пожаловать в бот!",
        reply_markup=kb.start_kb
    )
