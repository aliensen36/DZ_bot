from aiogram.filters import BaseFilter
from aiogram.types import Message
from typing import Union

class ChatTypeFilter(BaseFilter):
    def __init__(self, chat_types: Union[str, list[str]]):
        self.chat_types = [chat_types] if isinstance(chat_types, str) else chat_types

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self.chat_types


class IsGroupAdmin(BaseFilter):
    def __init__(self, admin_chat_id: int):
        self.admin_chat_id = admin_chat_id

    async def __call__(self, message: Message, bot: Bot) -> bool:
        # Для личных сообщений проверяем права в группе
        if message.chat.type == "private":
            try:
                member = await bot.get_chat_member(self.admin_chat_id, message.from_user.id)
                return member.status in ["creator", "administrator"]
            except:
                return False
        # Для групповых сообщений проверяем права в текущем чате
        else:
            try:
                member = await bot.get_chat_member(message.chat.id, message.from_user.id)
                return member.status in ["creator", "administrator"]
            except:
                return False
