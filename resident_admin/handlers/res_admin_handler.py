import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from client.services.loyalty import fetch_loyalty_card
from resident_admin.services.point_transactions import add_points_to_card, \
    find_user_by_card_number, get_card_number_by_user, find_user_by_phone
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
    """Состояния FSM для транзакций бонусов.

    States:
        phone_number: номер телефона покупателя
        price: сумма покупки.
        transaction_type: тип транзакции.
        resident_id: id резидента
    """
    number = State()
    transaction_type = State()
    price = State()
    resident_tg_id = State()
    
    
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

    # Форматируем входные данные
    if re.match(phone_pattern, input_text):
        phone_number = input_text.replace('+', '')  # Убираем + для единообразия
        logger.info(f"Processing phone_number: {phone_number}")
        user_data = await find_user_by_phone(phone_number)
        if user_data and user_data.get('tg_id'):
            card_data = await fetch_loyalty_card(user_data['tg_id'])
            if card_data and card_data.get('card_image'):
                card_number = await get_card_number_by_user(user_data['tg_id'])
                if card_number:
                    # Сохраняем данные в состоянии
                    await state.update_data(user_data=user_data, card_number=card_number)
                    # Отправляем изображение карты
                    await message.answer_photo(
                        photo=BufferedInputFile(card_data['card_image'], filename=f"card_{card_number}.png"),
                        caption=(
                            f"Карта найдена: {card_number} "
                            f"(Клиент: {user_data['user_first_name']} {user_data['user_last_name']}).\n"
                            f"Выберите тип транзакции (начисление или списание):"
                        )
                    )
                    await state.set_state(TransactionFSM.transaction_type)
                else:
                    await message.answer(
                        "Не удалось получить номер карты. Попробуйте ввести номер карты (формат: 123 456):"
                    )
                    await state.set_state(TransactionFSM.number)
            else:
                await message.answer(
                    "Карта не может быть сгенерирована по номеру телефона. Попробуйте ввести номер карты (формат: 123 456):"
                )
                await state.set_state(TransactionFSM.number)
        else:
            await message.answer(
                "Пользователь не найден по номеру телефона. Попробуйте ввести номер карты (формат: 123 456):"
            )
            await state.set_state(TransactionFSM.number)
    elif re.match(card_number_pattern, input_text):
        card_number = input_text.replace(' ', '')  # Убираем пробел для единообразия
        user_data = await find_user_by_card_number(card_number)
        if user_data and user_data.get('tg_id'):
            card_data = await fetch_loyalty_card(user_data['tg_id'])
            if card_data and card_data.get('card_image'):
                # Сохраняем данные в состоянии
                await state.update_data(user_data=user_data, card_number=card_number)
                # Отправляем изображение карты
                await message.answer_photo(
                    photo=BufferedInputFile(card_data['card_image'], filename=f"card_{card_number}.png"),
                    caption=(
                        f"Карта найдена: {card_number} "
                        f"(Клиент: {user_data['user_first_name']} {user_data['user_last_name']}).\n"
                        f"Выберите тип транзакции (начисление или списание):"
                    )
                )
                await state.set_state(TransactionFSM.transaction_type)
            else:
                await message.answer(
                    "Карта не может быть сгенерирована по номеру карты. Попробуйте еще раз или введите номер телефона:"
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


