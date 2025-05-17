import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, types
from typing import Optional
from data.config import config_settings

from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from admin.handlers.admin_handler import admin_router
from admin.handlers.mailing_handler import admin_mailing_router
from cmds.bot_cmds_list import bot_cmds_list
from handlers.profile_handler import profile_router
from handlers.start_handler import start_router

from utils.services import notify_restart
from dotenv import load_dotenv
logger = logging.getLogger(__name__)

load_dotenv()

TOKEN = os.getenv("TOKEN")

PROPERTIES = DefaultBotProperties(parse_mode=ParseMode.HTML)

bot = Bot(token=config_settings.TOKEN.get_secret_value(),
          default=PROPERTIES)

async def startup(dispatcher: Dispatcher):
    logger.info("Starting bot...")
    await notify_restart(bot, "работает")
    # try:
    #     await init_db()
    # except Exception as e:
    #     logger.error(f"Database error: {e}")
    #     raise


async def shutdown(dispatcher: Dispatcher):
    logger.info("Shutting down...")
    await notify_restart(bot, "остановлен")
    sys.exit(0)


def setup_routers(dp: Dispatcher) -> None:
    """Регистрация всех роутеров"""
    routers = (
        start_router,
        profile_router,
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
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
