import re

import aiohttp
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from client.services.loyalty import fetch_loyalty_card
from data.config import config_settings
from data.url import url_point_transactions_deduct, url_point_transactions_accrue
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

class TransactionFSM(StatesGroup):
    number = State()
    transaction_type = State()
    price = State()

    
@res_admin_router.message(Command("res_admin"))
async def resident_admin_panel(message: Message):
    await message.answer("Добро пожаловать в резидентскую админ-панель!",
                         reply_markup=res_admin_keyboard())


# Хендлер для команды "Бонусы"
@res_admin_router.message(F.text == 'Бонусы')
async def cmd_add_points(message: Message, state: FSMContext):
    await message.answer('Введите номер телефона покупателя (формат: 79998887766 или +79998887766) '
                         'или номер карты (формат: 123 456):')
    await state.set_state(TransactionFSM.number)


# Хендлер для обработки номера телефона или карты
@res_admin_router.message(TransactionFSM.number)
async def process_phone_or_card(message: Message, state: FSMContext):
    input_text = message.text.strip()

    # Проверка формата номера телефона
    phone_pattern = r'^\+?7\d{10}$'
    # Проверка формата номера карты (6 цифр, с пробелом или без)
    card_number_pattern = r'^\d{3}\s?\d{3}$'

    # Создаём инлайн-клавиатуру для выбора типа операции
    transaction_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Начисление", callback_data="transaction_accrue")],
        [InlineKeyboardButton(text="Списание", callback_data="transaction_deduct")]
    ])

    # Форматируем входные данные
    if re.match(phone_pattern, input_text):
        phone_number = input_text.replace('+', '')  # Убираем + для единообразия
        logger.info(f"Processing phone_number: {phone_number}")
        user_data = await find_user_by_phone(phone_number)
        if user_data and user_data.get('tg_id'):
            card_number = await get_card_number_by_user(user_data['tg_id'])
            if card_number:
                # Получаем card_id
                card_id = await get_card_id_by_tg_id(user_data['tg_id'])
                if card_id is None:
                    await message.answer(
                        "Не удалось получить данные карты. Попробуйте еще раз или введите номер телефона:"
                    )
                    await state.set_state(TransactionFSM.number)
                    return
                # Генерируем изображение карты
                card_data = await fetch_loyalty_card(user_data['tg_id'])
                if card_data and card_data.get('card_image'):
                    # Сохраняем данные в состоянии
                    await state.update_data(
                        user_data=user_data,
                        card_number=card_number,
                        card_id=card_id
                    )
                    # Отправляем изображение карты отдельно
                    await message.answer_photo(
                        photo=BufferedInputFile(card_data['card_image'], filename=f"card_{card_number}.png"),
                        caption=f"Карта найдена: {card_number} (Клиент: {user_data['user_first_name']} {user_data['user_last_name']})"
                    )
                    # Отправляем сообщение с выбором типа операции
                    await message.answer(
                        "Выберите тип операции:",
                        reply_markup=transaction_keyboard
                    )
                    await state.set_state(TransactionFSM.transaction_type)
                else:
                    await message.answer(
                        "Не удалось сгенерировать изображение карты. Попробуйте еще раз или введите номер телефона:"
                    )
                    await state.set_state(TransactionFSM.number)
            else:
                await message.answer(
                    "Карта не найдена для данного пользователя. Попробуйте ввести номер карты (формат: 123 456):"
                )
                await state.set_state(TransactionFSM.number)
        else:
            await message.answer(
                "Пользователь не найден по номеру телефона. Попробуйте ввести номер карты (формат: 123 456):"
            )
            await state.set_state(TransactionFSM.number)
    elif re.match(card_number_pattern, input_text):
        card_number = input_text.replace(' ', '')  # Убираем пробел для единообразия
        logger.info(f"Processing card_number: {card_number}")
        user_data = await find_user_by_card_number(card_number)
        if user_data and user_data.get('tg_id'):
            # Получаем card_id
            card_id = await get_card_id_by_tg_id(user_data['tg_id'])
            if card_id is None:
                await message.answer(
                    "Не удалось получить данные карты. Попробуйте еще раз или введите номер телефона:"
                )
                await state.set_state(TransactionFSM.number)
                return
            # Генерируем изображение карты
            card_data = await fetch_loyalty_card(user_data['tg_id'])
            if card_data and card_data.get('card_image'):
                # Сохраняем данные в состоянии
                await state.update_data(
                    user_data=user_data,
                    card_number=card_number,
                    card_id=card_id
                )
                # Отправляем изображение карты отдельно
                await message.answer_photo(
                    photo=BufferedInputFile(card_data['card_image'], filename=f"card_{card_number}.png"),
                    caption=f"Карта найдена: {card_number} (Клиент: {user_data['user_first_name']} {user_data['user_last_name']})"
                )
                # Отправляем сообщение с выбором типа операции
                await message.answer(
                    "Выберите тип операции:",
                    reply_markup=transaction_keyboard
                )
                await state.set_state(TransactionFSM.transaction_type)
            else:
                await message.answer(
                    "Не удалось сгенерировать изображение карты. Попробуйте еще раз или введите номер телефона:"
                )
                await state.set_state(TransactionFSM.number)
        else:
            await message.answer(
                "Пользователь не найден по номеру карты. Попробуйте еще раз или введите номер телефона:"
            )
            await state.set_state(TransactionFSM.number)
    else:
        await message.answer(
            "Неверный формат. Введите номер телефона (79998887766 или +79998887766) или номер карты (123 456):"
        )


@res_admin_router.callback_query(TransactionFSM.transaction_type)
async def process_transaction_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа транзакции (начисление или списание)."""
    if callback.data == "transaction_accrue":
        await callback.message.answer("Введите сумму для начисления баллов (в рублях):")
        await state.set_state(TransactionFSM.price)
        await state.update_data(transaction_type="accrue")
    elif callback.data == "transaction_deduct":
        await callback.message.answer("Введите сумму для списания баллов (в рублях):")
        await state.set_state(TransactionFSM.price)
        await state.update_data(transaction_type="deduct")
    await callback.answer()

@res_admin_router.message(TransactionFSM.price)
async def process_transaction_price(message: Message, state: FSMContext):
    """Обработка суммы для начисления или списания баллов."""
    try:
        price = float(message.text.strip())
        if price <= 0:
            await message.answer("Сумма должна быть положительной. Введите сумму ещё раз:")
            return
    except ValueError:
        await message.answer("Сумма должна быть числом. Введите сумму ещё раз:")
        return

    state_data = await state.get_data()
    card_id = state_data.get('card_id')
    transaction_type = state_data.get('transaction_type')
    card_number = state_data.get('card_number')
    user_data = state_data.get('user_data')

    if not card_id:
        await message.answer("Ошибка: ID карты не найден. Попробуйте начать заново.")
        await state.set_state(TransactionFSM.number)
        return

    # Получаем user_id через tg_id из user_data
    tg_id = user_data.get('tg_id') or message.from_user.id  # Используем message.from_user.id как запасной вариант
    if not tg_id:
        logger.error(f"No tg_id found in user_data: {user_data}")
        await message.answer("Ошибка: Telegram ID пользователя не найден. Попробуйте начать заново.")
        await state.set_state(TransactionFSM.number)
        return

    user_id = await get_user_id_by_tg_id(tg_id)
    if not user_id:
        logger.error(f"No user_id found for tg_id={tg_id}")
        await message.answer("Ошибка: ID пользователя не найден. Попробуйте начать заново.")
        await state.set_state(TransactionFSM.number)
        return

    resident_id = await get_resident_id_by_user_id(user_id)
    if not resident_id:
        logger.error(f"No resident_id found for user_id={user_id}")
        await message.answer("Ошибка: Резидент не найден. Попробуйте начать заново.")
        await state.set_state(TransactionFSM.number)
        return

    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    transaction_data = {
        'price': price,
        'card_id': card_id,
        'resident_id': resident_id
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            if transaction_type == "accrue":
                url = url_point_transactions_accrue
                async with session.post(url, headers=headers, json=transaction_data) as resp:
                    if resp.status == 201:
                        data = await resp.json()
                        points = data.get('points', 0)
                        await message.answer(
                            f"Начислено {points} баллов за сумму {price} руб. "
                            f"Карта: {card_number} (Клиент: {user_data['user_first_name']} {user_data['user_last_name']})"
                        )
                        await state.clear()
                    else:
                        error_data = await resp.json()
                        error_msg = error_data.get('error', 'Неизвестная ошибка при начислении баллов')
                        await message.answer(f"Ошибка: {error_msg}. Попробуйте ещё раз:")
                        await state.set_state(TransactionFSM.price)
            elif transaction_type == "deduct":
                url = url_point_transactions_deduct
                async with session.post(url, headers=headers, json=transaction_data) as resp:
                    if resp.status == 201:
                        data = await resp.json()
                        points = abs(data.get('points', 0))  # Учитываем отрицательное значение
                        await message.answer(
                            f"Списано {points} баллов за сумму {price} руб. "
                            f"Карта: {card_number} (Клиент: {user_data['user_first_name']} {user_data['user_last_name']})"
                        )
                        await state.clear()
                    else:
                        error_data = await resp.json()
                        error_msg = error_data.get('error', 'Неизвестная ошибка при списании баллов')
                        await message.answer(f"Ошибка: {error_msg}. Попробуйте ещё раз:")
                        await state.set_state(TransactionFSM.price)
    except aiohttp.ClientError as e:
        logger.error(f"Error processing transaction {transaction_type} for card_id={card_id}: {e}")
        await message.answer("Ошибка связи с сервером. Попробуйте ещё раз позже:")
        await state.set_state(TransactionFSM.price)
