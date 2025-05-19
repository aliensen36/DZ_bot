import logging
import aiohttp
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiohttp import ClientError, ClientConnectorError, ServerTimeoutError, ContentTypeError
import asyncio
from data.url import url_users
from keyboards.reply import main_kb

logger = logging.getLogger(__name__)

start_router = Router()


@start_router.message(CommandStart())
async def cmd_start(message: Message):
    user_data = {
        "tg_id": message.from_user.id,
        "first_name": message.from_user.first_name or "",
        "last_name": message.from_user.last_name or "",
        "username": message.from_user.username or "",
        "is_bot": message.from_user.is_bot,
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            try:
                async with session.post(url_users, json=user_data) as resp:
                    response_data = await resp.json()

                    # Основная логика для успешных ответов (200 или 201)
                    if resp.status in (200, 201):
                        greeting_name = response_data.get('first_name', message.from_user.first_name)

                        # Определяем текст приветствия
                        if resp.status == 201:
                            greeting_text = "Рады тебя видеть в нашем боте! 🤖💫"
                        else:  # 200
                            greeting_text = "С возвращением! Рады видеть вас снова! 🤗"

                        await message.answer(
                            f"✨ Привет, <b>{greeting_name}</b>! ✨\n\n"
                            f"{greeting_text}",
                            reply_markup=main_kb
                        )

                    # Обработка других статусов
                    else:
                        error_msg = response_data.get('detail', 'Сервис временно недоступен')
                        logger.error(f"API error {resp.status}: {error_msg}")
                        await message.answer(
                            f"Привет, <b>{message.from_user.first_name}</b>!\n"
                            f"⚠️ {error_msg}\n\n"
                            "Попробуйте позже или обратитесь в поддержку."
                        )

            except ServerTimeoutError:
                logger.error("Таймаут подключения к серверу")
                await message.answer(
                    f"⏳ <b>{message.from_user.first_name}</b>, сервер не отвечает.\n"
                    "Попробуйте через несколько минут."
                )

            except ClientConnectorError as e:
                logger.error(f"Ошибка подключения: {str(e)}")
                await message.answer(
                    f"🔌 <b>Технические неполадки</b>\n\n"
                    f"Привет, <b>{message.from_user.first_name}</b>!\n"
                    "Не удалось подключиться к серверу.\n\n"
                    "🛠️ Мы уже решаем проблему!\n"
                    "🕒 Попробуйте через 15-20 минут."
                )

            except Exception as e:
                logger.error(f"Ошибка запроса: {str(e)}")
                await message.answer(
                    f"🌀 <b>Неожиданная ошибка</b>\n\n"
                    f"Привет, <b>{message.from_user.first_name}</b>!\n"
                    "Произошла непредвиденная ошибка.\n\n"
                    "Наши специалисты уже в курсе и работают над решением."
                )

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
        await message.answer(
            f"👋 <b>{message.from_user.first_name}</b>, добро пожаловать!\n"
            "Сервис временно ограничен, но основные функции доступны.",
            reply_markup=main_kb
        )