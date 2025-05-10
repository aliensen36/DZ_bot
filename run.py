import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from database.engine import init_db, close_db
from handlers.user import user
from config import TOKEN, PROPERTIES

logger = logging.getLogger(__name__)
bot = Bot(token=TOKEN,
          default=PROPERTIES)


async def startup(dispatcher: Dispatcher):
    logger.info("Starting bot...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise


async def shutdown(dispatcher: Dispatcher):
    logger.info("Shutting down...")
    await close_db()
    sys.exit(0)


async def main():
    dp = Dispatcher()
    dp.include_router(user)
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
