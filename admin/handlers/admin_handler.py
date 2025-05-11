import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message

from admin.keyboards.admin_keyboards import admin_keyboard
from config import admin_chat_required

logger = logging.getLogger(__name__)

admin_router = Router()

@admin_router.message(Command("admin"))
@admin_chat_required
async def admin_panel(message: Message):
    logger.info(f"Admin access by {message.from_user.id}")
    await message.answer(
        "🛠 Админ-панель",
        reply_markup=admin_keyboard()
    )
