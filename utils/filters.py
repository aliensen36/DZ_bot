import os
from aiogram.filters import BaseFilter
from aiogram.types import Message
from typing import Union
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
RESIDENT_ADMIN_CHAT_ID = os.getenv("RESIDENT_ADMIN_CHAT_ID")


class ChatTypeFilter(BaseFilter):
    def __init__(self, chat_types: Union[str, list[str]]):
        """Фильтр для ограничения типа чата.

        Args:
            chat_types (Union[str, list[str]]): Типы чатов (например, "private") или список типов.

        Returns:
            bool: True, если тип чата соответствует, иначе False.
        """
        self.chat_types = [chat_types] if isinstance(chat_types, str) else chat_types

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self.chat_types


class IsGroupAdmin(BaseFilter):
    def __init__(self, admin_chat_ids: list[int], show_message: bool = True):
        self.admin_chat_ids = admin_chat_ids
        self.show_message = show_message

    async def __call__(self, message: Message, bot: Bot) -> bool:
        if message.chat.type == "private":
            try:
                for chat_id in self.admin_chat_ids:
                    member = await bot.get_chat_member(chat_id, message.from_user.id)
                    if member.status in ["creator", "administrator"]:
                        return True
                if self.show_message:
                    await message.answer("🚫 Доступ только для админов!")
                return False
            except Exception as e:
                if self.show_message:
                    await message.answer("⚠️ Ошибка проверки прав доступа")
                return False
        return False
