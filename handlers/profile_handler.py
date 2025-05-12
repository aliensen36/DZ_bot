from aiogram import Router
from aiogram.types import Message
from aiogram import F

from keyboards.inline import get_profile_inline_kb

profile_router = Router()

@profile_router.message(F.text == "Личный кабинет")
async def handle_profile(message: Message):
    await message.answer(
        "🔐 Ваш личный кабинет",
        reply_markup=await get_profile_inline_kb()
    )
