import re
import aiohttp
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from data.config import config_settings
from data.url import url_verify_pin
from resident_admin.keyboards.res_admin_reply import res_admin_keyboard
from utils.filters import ChatTypeFilter, RESIDENT_ADMIN_CHAT_ID
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import logging
logger = logging.getLogger(__name__)

res_admin_router = Router()
res_admin_router.message.filter(ChatTypeFilter("private"))

# FSM
class AdminAuth(StatesGroup):
    waiting_for_pin = State()


@res_admin_router.message(Command("res_admin"))
async def resident_admin_panel(message: Message, state: FSMContext, bot: Bot):
    try:
        member = await bot.get_chat_member(RESIDENT_ADMIN_CHAT_ID, message.from_user.id)
        if member.status not in ["administrator", "creator"]:
            await message.answer("🚫 Доступ только для резидентов!")
            return
    except Exception:
        await message.answer("⚠️ Ошибка проверки прав доступа")
        return

    await message.answer("Введите пин-код для входа в резидентскую админ-панель:")
    await state.set_state(AdminAuth.waiting_for_pin)



@res_admin_router.message(AdminAuth.waiting_for_pin)
async def process_pin_code(message: Message, state: FSMContext):
    pin_code = message.text.strip()
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}

    logger.info(f"Verifying pin code for user_id={message.from_user.id}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(url_verify_pin, json={'pin_code': pin_code}, headers=headers) as resp:
                data = await resp.json()

                if resp.status == 200 and data['status'] == 'success':
                    # Получаем ID и имя резидента
                    resident_id = data['resident']['id']
                    resident_name = data['resident']['name']

                    # Сохраняем в FSMContext
                    await state.update_data(
                        resident_id=resident_id,
                        resident_name=resident_name,
                    )

                    # Сообщаем об успешном входе и выводим резидента один раз
                    await message.answer(
                        "Вы вошли в административную панель резидента.",
                        reply_markup=res_admin_keyboard()
                    )
                    await message.answer(
                        f"Вы совершаете операции от имени <b>{resident_name}</b>",
                        parse_mode="HTML"
                    )

                    # Сбрасываем состояние
                    await state.set_state(None)
                else:
                    await message.answer("Неверный пин-код или отсутствуют права администратора.")

    except aiohttp.ClientError as e:
        logger.error(f"Error verifying pin code for user_id={message.from_user.id}: {str(e)}")
        await message.answer("Ошибка при проверке пин-кода. Попробуйте позже.")
        await state.clear()
