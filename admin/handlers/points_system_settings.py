import aiohttp
import logging
from datetime import datetime
from pydantic import ValidationError
from aiogram.exceptions import TelegramBadRequest
from aiogram import Bot, F, Router
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from data.config import config_settings
from admin.keyboards.admin_reply import admin_keyboard, points_system_settings_keyboard, cancel_keyboard, edit_points_system_settings_keyboard
from data.url import url_points_settings
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID

# Настройка логирования
logger = logging.getLogger(__name__)

admin_points_settings_router = Router()
admin_points_settings_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([ADMIN_CHAT_ID], show_message=False)
)

# Состояния FSM
class PointsSystemSettingsStates(StatesGroup):
    waiting_for_points_per_100_rubles = State()
    waiting_for_points_per_1_percent = State()
    waiting_for_new_user_points = State()

class EditPointsSystemSettingsStates(StatesGroup):
    choosing_field = State()
    waiting_for_points_per_100_rubles = State()
    waiting_for_points_per_1_percent = State()
    waiting_for_new_user_points = State()

# Функции для работы с API
async def get_points_system_settings():
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_points_settings}single/", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                logger.error(f"Failed to fetch settings, status={resp.status}")
                return []
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching settings: {e}")
        return []

async def update_points_system_settings(settings_id: int, updated_fields: dict):
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.patch(
                f"{url_points_settings}{settings_id}/",
                json=updated_fields,
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return True
                logger.error(f"Failed to update points system settings, status={resp.status}, response={await resp.text()}")
                return False
    except aiohttp.ClientError as e:
        logger.error(f"Error updating points system settings: {e}")
        return False

async def create_points_system_settings(settings_data: dict):
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(f"{url_points_settings}", json=settings_data, headers=headers) as resp:
                if resp.status == 201:
                    return True
                logger.error(f"Failed to create points system settings, status={resp.status}")
                return False
    except aiohttp.ClientError as e:
        logger.error(f"Error creating points system settings: {e}")
        return False

# Обработчики меню и отмены
@admin_points_settings_router.message(F.text == "Назад")
async def back_to_admin_menu(message: Message):
    await message.answer(
        "Вы вернулись в главное меню администратора.",
        reply_markup=admin_keyboard(),
        parse_mode=None
    )

@admin_points_settings_router.message(F.text == "Отмена", StateFilter(PointsSystemSettingsStates, EditPointsSystemSettingsStates))
async def cancel_promotion_action(message: Message, state: FSMContext):
    logger.debug(f"Cancel action requested by user {message.from_user.id} in state {await state.get_state()}")
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=points_system_settings_keyboard(),
        parse_mode=None
    )

# Обработчики создания и редактирования настроек бонусной системы
@admin_points_settings_router.message(F.text == "🔧 Настройки бонусной системы")
async def points_system_settings_menu(message: Message, state: FSMContext):
    settings = await get_points_system_settings()

    if not settings:
        await message.answer(
            "Настройки бонусной системы не найдены. Пожалуйста, создайте их.\n"
            "Введите количество бонусов, соответствующее 100 р.:",
            reply_markup=cancel_keyboard(),
            parse_mode=None
        )
        await state.set_state(PointsSystemSettingsStates.waiting_for_points_per_100_rubles)
    else:
        await message.answer(
            "Текущие настройки бонусной системы:\n"
            f"Бонусы за 100 рублей: {settings.get('points_per_100_rubles')}\n"
            f"Бонусы за 1% скидки: {settings.get('points_per_1_percent')}\n"
            f"Бонусы для нового пользователя: {settings.get('new_user_points', 0)}\n"
            "Выберите действие с настройками бонусной системы:",
            reply_markup=points_system_settings_keyboard(),
            parse_mode=None
        )
        await state.set_state(EditPointsSystemSettingsStates.choosing_field)

@admin_points_settings_router.message(F.text == "Изменить настройки", StateFilter(EditPointsSystemSettingsStates.choosing_field))
async def show_edit_points_settings_menu(message: Message, state: FSMContext):
    logger.debug(f"User {message.from_user.id} requested edit points system settings")
    settings = await get_points_system_settings()
    if not settings:
        await message.answer(
            "Ошибка: настройки не найдены.",
            reply_markup=admin_keyboard(),
            parse_mode=None
        )
        await state.clear()
        return
    await message.answer(
        "Выберите, что хотите изменить:",
        reply_markup=edit_points_system_settings_keyboard(),
        parse_mode=None
    )
    await state.set_state(EditPointsSystemSettingsStates.choosing_field)

@admin_points_settings_router.message(
    StateFilter(EditPointsSystemSettingsStates.choosing_field),
    F.text.in_(["Изменить бонусы за 100 рублей", "Изменить бонусы за 1% скидки", "Изменить бонусы за регистрацию нового пользователя"])
)
async def handle_field_selection(message: Message, state: FSMContext):
    logger.debug(f"User {message.from_user.id} selected field: {message.text}")
    if message.text == "Изменить бонусы за 100 рублей":
        await message.answer(
            "Введите новое значение для бонусов за 100 рублей:",
            reply_markup=cancel_keyboard(),
            parse_mode=None
        )
        await state.set_state(EditPointsSystemSettingsStates.waiting_for_points_per_100_rubles)
    elif message.text == "Изменить бонусы за 1% скидки":
        await message.answer(
            "Введите новое значение для бонусов за 1% скидки:",
            reply_markup=cancel_keyboard(),
            parse_mode=None
        )
        await state.set_state(EditPointsSystemSettingsStates.waiting_for_points_per_1_percent)
    elif message.text == "Изменить бонусы за регистрацию нового пользователя":
        await message.answer(
            "Введите количество бонусов, которые будут начислены новому пользователю при регистрации:",
            reply_markup=cancel_keyboard(),
            parse_mode=None
        )
        await state.set_state(EditPointsSystemSettingsStates.waiting_for_new_user_points)

@admin_points_settings_router.message(
    StateFilter(EditPointsSystemSettingsStates.waiting_for_points_per_100_rubles)
)
async def handle_edit_points_per_100_rubles(message: Message, state: FSMContext):
    try:
        points = int(message.text)
        if points <= 0:
            raise ValueError("Значение должно быть положительным числом.")
    except ValueError:
        await message.answer(
            "Введите положительное целое число.",
            parse_mode=None
        )
        return
    settings = await get_points_system_settings()
    if not settings:
        await message.answer(
            "Ошибка: настройки не найдены.",
            reply_markup=admin_keyboard(),
            parse_mode=None
        )
        await state.clear()
        return
    updated_fields = {
        "points_per_100_rubles": points,
        "points_per_1_percent": settings.get("points_per_1_percent")
    }
    success = await update_points_system_settings(settings.get("id"), updated_fields)
    await state.clear()
    if success:
        await message.answer(
            f"Бонусы за 100 рублей успешно изменены на {points}!",
            reply_markup=points_system_settings_keyboard(),
            parse_mode=None
        )
    else:
        await message.answer(
            "Ошибка при обновлении настроек. Попробуйте позже.",
            reply_markup=admin_keyboard(),
            parse_mode=None
        )

@admin_points_settings_router.message(
    StateFilter(EditPointsSystemSettingsStates.waiting_for_points_per_1_percent)
)
async def handle_edit_points_per_1_percent(message: Message, state: FSMContext):
    try:
        points = int(message.text)
        if points <= 0:
            raise ValueError("Значение должно быть положительным числом.")
    except ValueError:
        await message.answer(
            "Введите положительное целое число.",
            parse_mode=None
        )
        return
    settings = await get_points_system_settings()
    if not settings:
        await message.answer(
            "Ошибка: настройки не найдены.",
            reply_markup=admin_keyboard(),
            parse_mode=None
        )
        await state.clear()
        return
    updated_fields = {
        "points_per_100_rubles": settings.get("points_per_100_rubles"),
        "points_per_1_percent": points
    }
    success = await update_points_system_settings(settings.get("id"), updated_fields)
    await state.clear()
    if success:
        await message.answer(
            f"Бонусы за 1% скидки успешно изменены на {points}!",
            reply_markup=points_system_settings_keyboard(),
            parse_mode=None
        )
    else:
        await message.answer(
            "Ошибка при обновлении настроек. Попробуйте позже.",
            reply_markup=admin_keyboard(),
            parse_mode=None
        )

@admin_points_settings_router.message(
    StateFilter(EditPointsSystemSettingsStates.waiting_for_new_user_points)
)
async def handle_edit_new_user_points(message: Message, state: FSMContext):
    try:
        points = int(message.text)
        if points <= 0:
            raise ValueError("Значение должно быть положительным числом.")
    except ValueError:
        await message.answer(
            "Введите положительное целое число.",
            parse_mode=None
        )
        return
    settings = await get_points_system_settings()
    if not settings:
        await message.answer(
            "Ошибка: настройки не найдены.",
            reply_markup=admin_keyboard(),
            parse_mode=None
        )
        await state.clear()
        return
    updated_fields = {
        "new_user_points": points,
        "points_per_100_rubles": settings.get("points_per_100_rubles"),
        "points_per_1_percent": settings.get("points_per_1_percent")
    }
    success = await update_points_system_settings(settings.get("id"), updated_fields)
    await state.clear()
    if success:
        await message.answer(
            f"Бонусы для нового пользователя изменены на {points}!",
            reply_markup=points_system_settings_keyboard(),
            parse_mode=None
        )
    else:
        await message.answer(
            "Ошибка при обновлении настроек. Попробуйте позже.",
            reply_markup=admin_keyboard(),
            parse_mode=None
        )

@admin_points_settings_router.message(StateFilter(PointsSystemSettingsStates.waiting_for_points_per_100_rubles))
async def handle_points_per_100_rubles(message: Message, state: FSMContext):
    try:
        points = int(message.text)
        if points <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "Введите положительное целое число.",
            parse_mode=None
        )
        return
    await state.update_data(points_per_100_rubles=points)
    await message.answer(
        "Введите количество бонусов, соответствующее 1% скидки:",
        parse_mode=None
    )
    await state.set_state(PointsSystemSettingsStates.waiting_for_points_per_1_percent)

@admin_points_settings_router.message(StateFilter(PointsSystemSettingsStates.waiting_for_points_per_1_percent))
async def handle_points_per_1_percent(message: Message, state: FSMContext):
    try:
        points = int(message.text)
        if points <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "Введите положительное целое число.",
            parse_mode=None
        )
        return
    await state.update_data(points_per_1_percent=points)
    await message.answer(
        "Введите количество бонусов для нового пользователя:",
        parse_mode=None
    )
    await state.set_state(PointsSystemSettingsStates.waiting_for_new_user_points)

@admin_points_settings_router.message(StateFilter(PointsSystemSettingsStates.waiting_for_new_user_points))
async def handle_new_user_points(message: Message, state: FSMContext):
    try:
        points = int(message.text)
        if points <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "Введите положительное целое число.",
            parse_mode=None
        )
        return
    await state.update_data(new_user_points=points)
    data = await state.get_data()
    success = await create_points_system_settings({
        "points_per_100_rubles": data["points_per_100_rubles"],
        "points_per_1_percent": data["points_per_1_percent"],
        "new_user_poinrs": data["new_user_points"]
    })
    await state.clear()
    if success:
        await message.answer(
            "Настройки бонусной системы успешно созданы:\n"
            f"Бонусы за 100 рублей: {data.get('points_per_100_rubles')}\n"
            f"Бонусы за 1% скидки: {data.get('points_per_1_percent')}\n"
            f"Бонусы для нового пользователя: {data.get('new_user_points', 0)}\n"
            "Выберите действие с настройками бонусной системы:",
            reply_markup=points_system_settings_keyboard(),
            parse_mode=None
        )
    else:
        await message.answer(
            "Ошибка при создании настроек. Попробуйте позже.",
            reply_markup=admin_keyboard(),
            parse_mode=None
        )