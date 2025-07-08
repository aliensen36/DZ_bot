import re

import aiohttp
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from client.services.loyalty import fetch_loyalty_card
from data.config import config_settings
from data.url import url_point_transactions_deduct, url_point_transactions_accrue, url_resident
from resident_admin.services.point_transactions import find_user_by_card_number, get_card_number_by_user, \
    find_user_by_phone, get_card_id_by_tg_id, get_resident_id_by_user_id, get_user_id_by_tg_id
from resident_admin.keyboards.res_admin_reply import res_admin_keyboard
from utils.filters import ChatTypeFilter, IsGroupAdmin, RESIDENT_ADMIN_CHAT_ID
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import logging
logger = logging.getLogger(__name__)

res_admin_router = Router()
res_admin_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([RESIDENT_ADMIN_CHAT_ID], show_message=False)
)

class AdminAuth(StatesGroup):
    waiting_for_pin = State()


@res_admin_router.message(Command("res_admin"))
async def resident_admin_panel(message: Message, state: FSMContext):
    await message.answer("Введите пин-код для входа в резидентскую админ-панель:")
    await state.set_state(AdminAuth.waiting_for_pin)


@res_admin_router.message(AdminAuth.waiting_for_pin)
async def process_pin_code(message: Message, state: FSMContext):
    pin_code = message.text.strip()
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    url_verify_pin = f"{url_resident}verify-pin/"

    logger.info(f"Verifying pin code for user_id={message.from_user.id}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(url_verify_pin, json={'pin_code': pin_code}, headers=headers) as resp:
                data = await resp.json()

                if resp.status == 200 and data['status'] == 'success':
                    # Сохраняем данные резидента в состоянии
                    await state.update_data(resident_id=data['resident']['id'])
                    await message.answer(
                        "Вход в резидентскую админ-панель успешен!",
                        reply_markup=res_admin_keyboard()
                    )
                else:
                    await message.answer("Неверный пин-код или отсутствуют права администратора.")

                await state.clear()
    except aiohttp.ClientError as e:
        logger.error(f"Error verifying pin code for user_id={message.from_user.id}: {str(e)}")
        await message.answer("Произошла ошибка при проверке пин-кода. Попробуйте позже.")
        await state.clear()
