import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, types
from typing import Optional

from admin.handlers.admin_handler import admin_router
from cmds.bot_cmds_list import bot_cmds_list
from database.engine import init_db, close_db
from handlers.start_handler import start_router
from config import TOKEN, PROPERTIES, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN,
          default=PROPERTIES)

async def send_to_chat(text: str, chat_id: Optional[int] = None):
    """
    Функция для отправки сообщений в чат админов
    :param text: Текст сообщения
    :param chat_id: ID чата (если None, используется CHAT_ID из переменных окружения)
    """
    target_chat_id = chat_id or ADMIN_CHAT_ID
    if target_chat_id is None:
        logging.error("Не указан chat_id для отправки сообщения")
        return

    try:
        await bot.send_message(chat_id=target_chat_id, text=text)
    except Exception as e:
        logging.error(f"Ошибка отправки в чат {target_chat_id}: {e}")


async def startup(dispatcher: Dispatcher):
    logger.info("Starting bot...")
    if ADMIN_CHAT_ID is not None:
        await send_to_chat(text="🔄 Бот был перезапущен!")
    else:
        logging.warning("ADMIN_CHAT_ID не установлен. "
                        "Уведомление о перезапуске не отправлено.")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise


async def shutdown(dispatcher: Dispatcher):
    logger.info("Shutting down...")
    await close_db()
    sys.exit(0)


def setup_routers(dp: Dispatcher) -> None:
    """Регистрация всех роутеров"""
    routers = (
        start_router,
        admin_router,
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
