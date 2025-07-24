import re
import aiohttp
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from client.services.loyalty import fetch_loyalty_card
from data.config import config_settings
from data.url import url_point_transactions_deduct, url_point_transactions_accrue, url_resident
from resident_admin.keyboards.res_admin_reply import back_to_menu_kb, res_admin_keyboard
from resident_admin.services.point_transactions import find_user_by_card_number, get_card_number_by_user, \
    find_user_by_phone, get_card_id_by_tg_id, get_user_id_by_tg_id
from resident_admin.services.resident_required import resident_required
from utils.filters import ChatTypeFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import logging
logger = logging.getLogger(__name__)

RA_bonus_router = Router()
RA_bonus_router.message.filter(ChatTypeFilter("private"))


class TransactionFSM(StatesGroup):
    number = State()
    transaction_type = State()
    price = State()


@RA_bonus_router.message(F.text == '↩ Обратно')
@resident_required
async def back_to_resident_menu(message: Message, state: FSMContext):
    await state.set_state(None)
    await message.answer("Главное меню",
                         reply_markup=res_admin_keyboard())


# Хендлер для команды "Бонусы"
@RA_bonus_router.message(F.text == 'Бонусы')
@resident_required
async def start_bonus_transaction(message: Message, state: FSMContext):
    await message.answer('Введите номер телефона покупателя (формат: 79998887766 или +79998887766) '
                         'или номер карты (формат: 123 456):',
                          reply_markup=back_to_menu_kb)
    await state.set_state(TransactionFSM.number)


# Хендлер для обработки номера телефона или карты
@RA_bonus_router.message(TransactionFSM.number)
@resident_required
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
                        "Не удалось получить данные карты. Попробуйте еще раз или введите номер телефона:",
                          reply_markup=back_to_menu_kb
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
                    await message.answer("Для возврата в главное меню нажмите кнопку '↩ Обратно'.",
                                         reply_markup=back_to_menu_kb)
                    # Отправляем изображение карты отдельно
                    await message.answer_photo(
                        photo=BufferedInputFile(card_data['card_image'], filename=f"card_{card_number}.png"),
                        caption=f"Карта найдена: {card_number} (Клиент: {user_data['user_first_name']} {user_data['user_last_name']})",
                        reply_markup=back_to_menu_kb
                    )
                    # Отправляем сообщение с выбором типа операции
                    await message.answer(
                        "Выберите тип операции:",
                        reply_markup=transaction_keyboard
                    )
                    await state.set_state(TransactionFSM.transaction_type)
                else:
                    await message.answer(
                        "Не удалось сгенерировать изображение карты. Попробуйте еще раз или введите номер телефона:",
                        reply_markup=back_to_menu_kb
                    )
                    await state.set_state(TransactionFSM.number)
            else:
                await message.answer(
                    "Карта не найдена для данного пользователя. Попробуйте ввести номер карты (формат: 123 456):",
                    reply_markup=back_to_menu_kb
                )
                await state.set_state(TransactionFSM.number)
        else:
            await message.answer(
                "Пользователь не найден по номеру телефона. Попробуйте ввести номер карты (формат: 123 456):",
                reply_markup=back_to_menu_kb
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
                    "Не удалось получить данные карты. Попробуйте еще раз или введите номер телефона:",
                    reply_markup=back_to_menu_kb
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
                await message.answer("Для возврата в главное меню нажмите кнопку '↩ Обратно'.",
                                     reply_markup=back_to_menu_kb)
                # Отправляем изображение карты отдельно
                await message.answer_photo(
                    photo=BufferedInputFile(card_data['card_image'], filename=f"card_{card_number}.png"),
                    caption=f"Карта найдена: {card_number} (Клиент: {user_data['user_first_name']} {user_data['user_last_name']})",
                    reply_markup=back_to_menu_kb
                )
                # Отправляем сообщение с выбором типа операции
                await message.answer(
                    "Выберите тип операции:",
                    reply_markup=transaction_keyboard
                )
                await state.set_state(TransactionFSM.transaction_type)
            else:
                await message.answer(
                    "Не удалось сгенерировать изображение карты. Попробуйте еще раз или введите номер телефона:",
                    reply_markup=back_to_menu_kb
                )
                await state.set_state(TransactionFSM.number)
        else:
            await message.answer(
                "Пользователь не найден по номеру карты. Попробуйте еще раз или введите номер телефона:",
                reply_markup=back_to_menu_kb
            )
            await state.set_state(TransactionFSM.number)
    else:
        await message.answer(
            "Неверный формат. Введите номер телефона (79998887766 или +79998887766) или номер карты (123 456):",
            reply_markup=back_to_menu_kb
        )


@RA_bonus_router.callback_query(TransactionFSM.transaction_type)
@resident_required
async def process_transaction_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа транзакции (начисление или списание)."""
    if callback.data == "transaction_accrue":
        await callback.message.answer(
            "Введите сумму покупки для начисления баллов (в рублях):",
            reply_markup=back_to_menu_kb)
        await state.set_state(TransactionFSM.price)
        await state.update_data(transaction_type="accrue")
    elif callback.data == "transaction_deduct":
        await callback.message.answer(
            "Введите сумму покупки для списания баллов (в рублях):",
            reply_markup=back_to_menu_kb)
        await state.set_state(TransactionFSM.price)
        await state.update_data(transaction_type="deduct")
    await callback.answer()


@RA_bonus_router.message(TransactionFSM.price)
@resident_required
async def process_transaction_price(message: Message, state: FSMContext):
    """Обработка суммы для начисления или списания баллов."""
    try:
        price = float(message.text.strip())
        if price <= 0:
            await message.answer(
                "Сумма должна быть положительной. Введите сумму ещё раз:",
                reply_markup=back_to_menu_kb)
            return
    except ValueError:
        await message.answer(
            "Сумма должна быть числом. Введите сумму ещё раз:",
            reply_markup=back_to_menu_kb)
        return

    state_data = await state.get_data()
    card_id = state_data.get('card_id')
    transaction_type = state_data.get('transaction_type')
    card_number = state_data.get('card_number')
    user_data = state_data.get('user_data')

    if not card_id:
        await message.answer(
            "Ошибка: ID карты не найден. Попробуйте начать заново.",
            reply_markup=back_to_menu_kb)
        await state.set_state(TransactionFSM.number)
        return

    # Получаем user_id через tg_id из user_data
    tg_id = user_data.get('tg_id') or message.from_user.id
    if not tg_id:
        logger.error(f"No tg_id found in user_data: {user_data}")
        await message.answer(
            "Ошибка: Telegram ID пользователя не найден. Попробуйте начать заново.",
            reply_markup=back_to_menu_kb)
        await state.set_state(TransactionFSM.number)
        return

    user_id = await get_user_id_by_tg_id(tg_id)
    if not user_id:
        logger.error(f"No user_id found for tg_id={tg_id}")
        await message.answer(
            "Ошибка: ID пользователя не найден. Попробуйте начать заново.",
            reply_markup=back_to_menu_kb)
        await state.set_state(TransactionFSM.number)
        return

    resident_id = state_data.get('resident_id')
    if not resident_id:
        await message.answer(
            "Ошибка: резидент не определён. Войдите заново.",
            reply_markup=back_to_menu_kb)
        await state.set_state(TransactionFSM.number)
        return

    headers = {
        "X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value(),
        "X-Resident-ID": str(resident_id)
    }

    transaction_data = {
        'price': price,
        'card_id': card_id
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            if transaction_type == "accrue":
                url = url_point_transactions_accrue
                async with session.post(url, headers=headers, json=transaction_data) as resp:
                    if resp.status == 201:
                        data = await resp.json()
                        points = data.get('points', 0)
                        # Генерируем изображение карты
                        card_data = await fetch_loyalty_card(tg_id)
                        if card_data and card_data.get('card_image'):
                            # Отправляем изображение карты
                            await message.answer_photo(
                                photo=BufferedInputFile(card_data['card_image'], filename=f"card_{card_number}.png"),
                                caption=(
                                    f"Начислено баллов: <b>{points}</b>\n\n"
                                    f"за покупку на сумму <b>{price}</b> руб.\n\n"
                                    f"Карта: {card_number} (Клиент: {user_data['user_first_name']} {user_data['user_last_name']})"
                                ),
                                reply_markup=back_to_menu_kb
                            )
                        else:
                            # Если изображение не удалось получить, отправляем только текст
                            await message.answer(
                                f"Начислено баллов: <b>{points}</b>\n\n"
                                f"за покупку на сумму <b>{price}</b> руб.\n\n"
                                f"Карта: {card_number} (Клиент: {user_data['user_first_name']} {user_data['user_last_name']})",
                                reply_markup=back_to_menu_kb)
                        await state.set_state(None)
                    else:
                        error_data = await resp.json()
                        error_msg = error_data.get('error', 'Неизвестная ошибка при начислении баллов')
                        await message.answer(f"Ошибка:\n"
                                             f"<b>{error_msg}</b>.\n"
                                             f"Попробуйте ещё раз.",
                                             reply_markup=back_to_menu_kb)
                        await state.set_state(TransactionFSM.price)
            elif transaction_type == "deduct":
                url = url_point_transactions_deduct
                async with session.post(url, headers=headers, json=transaction_data) as resp:
                    if resp.status == 201:
                        data = await resp.json()
                        points = abs(data.get('points', 0))
                        # Генерируем изображение карты
                        card_data = await fetch_loyalty_card(tg_id)
                        if card_data and card_data.get('card_image'):
                            # Отправляем изображение карты
                            await message.answer_photo(
                                photo=BufferedInputFile(card_data['card_image'], filename=f"card_{card_number}.png"),
                                caption=(
                                    f"Списано баллов: <b>{points}</b>\n\n"
                                    f"за покупку на сумму <b>{price}</b> руб.\n\n"
                                    f"Карта: {card_number} (Клиент: {user_data['user_first_name']} {user_data['user_last_name']})"
                                ),
                                reply_markup=back_to_menu_kb
                            )
                        else:
                            # Если изображение не удалось получить, отправляем только текст
                            await message.answer(
                                f"Списано баллов: <b>{points}</b>\n\n"
                                f"за покупку на сумму <b>{price}</b> руб.\n\n"
                                f"Карта: {card_number} (Клиент: {user_data['user_first_name']} {user_data['user_last_name']})",
                                reply_markup=back_to_menu_kb
                            )
                        await state.set_state(None)
                    else:
                        error_data = await resp.json()
                        error_msg = error_data.get('error', 'Неизвестная ошибка при списании баллов')
                        await message.answer(f"Ошибка:\n"
                                             f"<b>{error_msg}</b>.\n"
                                             f"Попробуйте ещё раз.",
                                             reply_markup=back_to_menu_kb)
                        await state.set_state(TransactionFSM.price)
    except aiohttp.ClientError as e:
        logger.error(f"Error processing transaction {transaction_type} for card_id={card_id}: {e}")
        await message.answer(
            "Ошибка связи с сервером. Попробуйте ещё раз позже:",
            reply_markup=back_to_menu_kb)
        await state.set_state(TransactionFSM.price)
