import os
from aiogram.filters import BaseFilter
from aiogram.types import Message
from typing import Union
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

class ChatTypeFilter(BaseFilter):
    def __init__(self, chat_types: Union[str, list[str]]):
        self.chat_types = [chat_types] if isinstance(chat_types, str) else chat_types

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self.chat_types


class IsGroupAdmin(BaseFilter):
    def __init__(self, admin_chat_id: int, show_message: bool = True):
        self.admin_chat_id = admin_chat_id
        self.show_message = show_message  # Флаг для отображения сообщения

    async def __call__(self, message: Message, bot: Bot) -> bool:
        if message.chat.type == "private":
            try:
                member = await bot.get_chat_member(self.admin_chat_id, message.from_user.id)
                if member.status not in ["creator", "administrator"]:
                    if self.show_message:  # Показываем сообщение только если флаг True
                        await message.answer("🚫 Доступ только для админов!")
                    return False
                return True
            except Exception as e:
                if self.show_message:
                    await message.answer("⚠️ Ошибка проверки прав доступа")
                return False
        return False
