import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from app.database.requests import create_user

import app.keyboards as kb


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
