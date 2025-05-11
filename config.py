import os
from functools import wraps

from aiogram import Bot, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

PROPERTIES = DefaultBotProperties(parse_mode=ParseMode.HTML)


DB_URL = os.getenv("DB_URL")
#DB_HOST = os.getenv("DB_HOST")
#DB_PORT = os.getenv("DB_PORT")
#DB_USER = os.getenv("DB_USER")
#DB_PASS = os.getenv("DB_PASS")
#DB_NAME = os.getenv("DB_NAME")

 # sqlite
TORTOISE_ORM = {
    "connections": {
        "default": DB_URL,
    },
    "apps": {
        "models": {
            "models": ["database.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}

# postgres
#TORTOISE_ORM = {
#   "connections": {
#        "default": {
#            "engine": "tortoise.backends.asyncpg",
#            "credentials": {
#                "host": DB_HOST,
#                "port": DB_PORT,
#                "user": DB_USER,
#                "password": DB_PASS,
#                "database": DB_NAME,
#            },
#        }
#    },
#    "apps": {
#        "models": {
#            "models": ["app.database.models", "aerich.models"],
#            "default_connection": "default",
#        }
#    },
#}


async def is_chat_admin(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(ADMIN_CHAT_ID, user_id)
        return member.status in ["creator", "administrator"]
    except:
        return False


def admin_chat_required(func):
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        if not await is_chat_admin(message.bot, message.from_user.id):
            return await message.answer("🚫 Доступ только для админов!")
        return await func(message, *args, **kwargs)
    return wrapper
