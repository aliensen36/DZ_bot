import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, types
from typing import Optional

from admin.handlers.admin_handler import admin_router
from admin.handlers.mailing_handler import admin_mailing_router
from cmds.bot_cmds_list import bot_cmds_list
from database.engine import init_db, close_db
from handlers.start_handler import start_router
from config import TOKEN, PROPERTIES, ADMIN_CHAT_ID
from utils.services import notify_restart

logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN,
          default=PROPERTIES)

async def startup(dispatcher: Dispatcher):
    logger.info("Starting bot...")
    await notify_restart(bot, "работает")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise


async def shutdown(dispatcher: Dispatcher):
    logger.info("Shutting down...")
    await notify_restart(bot, "остановлен")
    await close_db()
    sys.exit(0)


def setup_routers(dp: Dispatcher) -> None:
    """Регистрация всех роутеров"""
    routers = (
        start_router,
        admin_router,
        admin_mailing_router,
    )
    for router in routers:
        dp.include_router(router)


async def main():
    dp = Dispatcher()
    await bot.set_my_commands(commands=bot_cmds_list,
                              scope=types.BotCommandScopeAllPrivateChats())
    setup_routers(dp) # Загрузка роутеров
    dp.startup.register(startup)
    dp.shutdown.register(shutdown)

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
