import logging

from aiogram import Router, F
from aiogram.types import (
    Message, BufferedInputFile,
    ReplyKeyboardMarkup, KeyboardButton,
    CallbackQuery, ReplyKeyboardRemove
)

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp

from client.keyboards.reply import main_kb
from client.services.loyalty import fetch_loyalty_card, get_user_data
from client.services.user import update_user_data
from client.keyboards.reply import cancel_keyboard
from data.config import config_settings
from utils.validators import name_pattern, email_pattern
from utils.client_utils import parse_birth_date, normalize_phone_number

logger = logging.getLogger(__name__)

loyalty_router = Router()

# FSM состояния для процесса регистрации карты лояльности
class LoyaltyCardForm(StatesGroup):
    last_name = State()
    first_name = State()
    birth_date = State()
    phone_number = State()
    email = State()


# Обработчик команды "Отменить", возвращает в главное меню
@loyalty_router.message(F.text == "Отменить")
async def go_back_to_main_menu(message: Message):
    await message.answer("Вы вернулись в главное меню", reply_markup=main_kb)


# Запускает процесс регистрации карты лояльности при нажатии на кнопку.
@loyalty_router.callback_query(F.data == "loyalty_register")
async def start_loyalty_registration(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await handle_loyalty_request(callback.message, state)


# Хэндлер для кнопки "Карта лояльности"
@loyalty_router.message(F.text == "Карта лояльности")
async def handle_loyalty_request(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()

    try:
        user_data = await get_user_data(user_id)
        required_fields = ["user_first_name", "user_last_name", "birth_date", "phone_number", "email"]

        missing_fields = [field for field in required_fields if not user_data.get(field)]
        if missing_fields:
            logger.info(f"Missing fields for user {user_id}: {missing_fields}")
            await message.answer("Чтобы получить карту лояльности, пожалуйста, заполните недостающие данные.")
            if "user_last_name" in missing_fields:
                await state.set_state(LoyaltyCardForm.last_name)
                await message.answer("Введите вашу фамилию:", reply_markup=cancel_keyboard)
            elif "user_first_name" in missing_fields:
                await state.set_state(LoyaltyCardForm.first_name)
                await message.answer("Введите ваше имя:", reply_markup=cancel_keyboard)
            elif "birth_date" in missing_fields:
                await state.set_state(LoyaltyCardForm.birth_date)
                await message.answer("Введите дату рождения (в формате ДД.ММ.ГГГГ):", reply_markup=cancel_keyboard)
            elif "phone_number" in missing_fields:
                await state.set_state(LoyaltyCardForm.phone_number)
                keyboard = ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="Поделиться номером", request_contact=True)],
                        [KeyboardButton(text="Отменить")]
                    ],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
                await message.answer("Введите ваш номер телефона или нажмите кнопку ниже:", reply_markup=keyboard)
            elif "email" in missing_fields:
                await state.set_state(LoyaltyCardForm.email)
                await message.answer("Введите ваш email:", reply_markup=cancel_keyboard)
            return

        card = await fetch_loyalty_card(user_id)
        if card and (img_bytes := card.get("card_image")):
            image = BufferedInputFile(img_bytes, filename="loyalty_card.png")
            await message.answer_photo(photo=image, reply_markup=main_kb)
            logger.info(f"Sent dynamically generated loyalty card for user_id={user_id}")
        else:
            logger.warning(f"No card image available for user_id={user_id}")
            await message.answer("Карта не может быть сгенерирована. Попробуйте позже или обратитесь в поддержку.",
                                 reply_markup=main_kb)

    except Exception as e:
        logger.exception(f"Error handling loyalty card for user_id={user_id}: {str(e)}")
        await message.answer("Произошла ошибка. Попробуйте позже или обратитесь в поддержку.", reply_markup=main_kb)


# Обрабатывает ввод фамилии пользователя, проверяет корректность и сохраняет в состояние FSM.
@loyalty_router.message(LoyaltyCardForm.last_name)
async def collect_last_name(message: Message, state: FSMContext):
    if not name_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Фамилия должна содержать только буквы и быть не короче 2 символов. Попробуйте снова:")
        return
    await state.update_data(user_last_name=message.text.strip())
    await state.set_state(LoyaltyCardForm.first_name)
    await message.answer("Введите ваше имя:", reply_markup=cancel_keyboard)

@loyalty_router.message(LoyaltyCardForm.first_name)
async def collect_first_name(message: Message, state: FSMContext):
    if not name_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Имя должно содержать только буквы и быть не короче 2 символов. Попробуйте снова:")
        return
    await state.update_data(user_first_name=message.text.strip())
    await state.set_state(LoyaltyCardForm.birth_date)
    await message.answer("Введите дату рождения (в формате ДД.ММ.ГГГГ):", reply_markup=cancel_keyboard)

@loyalty_router.message(LoyaltyCardForm.birth_date)
async def collect_birth_date(message: Message, state: FSMContext):
    parsed_date = parse_birth_date(message.text)
    if not parsed_date:
        await message.answer("⚠️ Неверный формат. Попробуйте снова (ДД.ММ.ГГГГ):")
        return
    await state.update_data(birth_date=parsed_date)
    await state.set_state(LoyaltyCardForm.phone_number)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться номером", request_contact=True)],
            [KeyboardButton(text="Отменить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Введите ваш номер телефона или нажмите кнопку ниже:", reply_markup=keyboard)

@loyalty_router.message(LoyaltyCardForm.phone_number)
async def collect_phone_number(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()

    normalized_phone = normalize_phone_number(phone)
    if not normalized_phone:
        await message.answer(
            "⚠️ Введите корректный номер телефона с кодом страны, например: +79001234567",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    await state.update_data(phone_number=normalized_phone)
    await state.set_state(LoyaltyCardForm.email)
    await message.answer("Введите ваш email:", reply_markup=cancel_keyboard)

@loyalty_router.message(LoyaltyCardForm.email)
async def collect_email_and_create(message: Message, state: FSMContext):
    if not email_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Неверный формат email. Попробуйте снова:", reply_markup=cancel_keyboard)
        return

    await state.update_data(email=message.text.strip())
    data = await state.get_data()
    user_id = message.from_user.id
    logger.info(f"Collected data for user_id={user_id}: {data}")

    try:
        await update_user_data(
            user_id=user_id,
            first_name=data.get("user_first_name"),
            last_name=data.get("user_last_name"),
            birth_date=data.get("birth_date"),
            phone_number=data.get("phone_number"),
            email=data.get("email")
        )
        await state.clear()

        card = await fetch_loyalty_card(user_id)
        if card and (img_bytes := card.get("card_image")):
            image = BufferedInputFile(img_bytes, filename="loyalty_card.png")
            await message.answer_photo(photo=image, reply_markup=main_kb)
            logger.info(f"Sent loyalty card image for user_id={user_id}")
        else:
            logger.warning(f"No card image available for user_id={user_id}")
            await message.answer("Карта не может быть сгенерирована. Попробуйте позже.", reply_markup=main_kb)

    except Exception as e:
        logger.exception(f"Error finalizing loyalty card for user_id={user_id}: {str(e)}")
        await message.answer("Ошибка при сохранении данных. Попробуйте позже.", reply_markup=main_kb)
