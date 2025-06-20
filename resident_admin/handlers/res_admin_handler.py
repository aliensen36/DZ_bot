import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from resident_admin.keyboards.res_admin_reply import res_admin_keyboard
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID, RESIDENT_ADMIN_CHAT_ID

logger = logging.getLogger(__name__)


res_admin_router = Router()
res_admin_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([RESIDENT_ADMIN_CHAT_ID], show_message=False)
)


@res_admin_router.message(Command("res_admin"))
async def resident_admin_panel(message: Message):
    await message.answer("Добро пожаловать в резидентскую админ-панель!",
                         reply_markup=res_admin_keyboard())
