import logging
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from resident_admin.services.point_transactions import accrue_points, deduct_points
from resident_admin.keyboards.res_admin_reply import res_admin_keyboard
from utils.filters import ChatTypeFilter, IsGroupAdmin, RESIDENT_ADMIN_CHAT_ID
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logger = logging.getLogger(__name__)

res_admin_router = Router()
res_admin_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([RESIDENT_ADMIN_CHAT_ID], show_message=False)
)

class TransactionFSM(StatesGroup):
    """Состояния FSM для транзакций бонусов.

    States:
        card_id: id карты лояльности.
        price: сумма покупки.
        transaction_type: тип транзакции.
        resident_id: id резидента
    """
    phone_number = State()
    card_id = State()
    price = State()
    transaction_type = State()
    resident_tg_id = State()
    
    
@res_admin_router.message(Command("res_admin"))
async def resident_admin_panel(message: Message):
    await message.answer("Добро пожаловать в резидентскую админ-панель!",
                         reply_markup=res_admin_keyboard())


@res_admin_router.message(F.text == 'Начислить баллы')
async def cmd_add_points(message: Message, state: FSMContext):
    await message.answer('Введите номер телефона покупателя (формат: 79998887766 или +79998887766):')
    await state.set_state(TransactionFSM.phone_number)
    await state.update_data(transaction_type='начисление')


@res_admin_router.message(TransactionFSM.phone_number)
async def process_phone_number(message: Message, state: FSMContext):
    phone_number = message.text.strip()

    # Проверка корректности номера телефона
    if not re.fullmatch(r'^(\+7|7|8)\d{10}$', phone_number):
        await message.answer(
            'Некорректный формат номера. Пожалуйста, введите номер в формате 79998887766 или +79998887766:')
        return

    # Нормализация номера (приводим к формату 7XXXXXXXXXX)
    if phone_number.startswith('+7'):
        normalized_phone = phone_number[1:]
    elif phone_number.startswith('8'):
        normalized_phone = '7' + phone_number[1:]
    else:
        normalized_phone = phone_number

    await state.update_data(phone=normalized_phone)
    await message.answer('Введите сумму покупки:')
    await state.set_state(TransactionFSM.price)



@res_admin_router.message(F.text == 'Начислить баллы')
async def cmd_add_points(message: Message, state: FSMContext):
    await message.answer('Введите сумму покупки:')
    await state.set_state(TransactionFSM.price)
    await state.update_data(transaction_type='начисление')
    
@res_admin_router.message(F.text == 'Списать баллы')
async def cmd_deduct_points(message: Message, state: FSMContext):
    await message.answer('Введите сумму для списания (₽):')
    await state.set_state(TransactionFSM.price)
    await state.update_data(transaction_type='списание')

    
@res_admin_router.message(TransactionFSM.price)
async def get_price_points(message: Message, state: FSMContext):
    message_text = message.text
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Сумма должна быть положительным числом!")
        return

    await state.update_data(price = message_text)
    await message.answer('введите номер карты лояльности')
    await state.set_state(TransactionFSM.card_id)

@res_admin_router.message(TransactionFSM.card_id)
async def get_card_id(message: Message, state: FSMContext):
    message_text = message.text
    import re
    CARD_RE = re.compile(r"^\d{3}-\d{3}-\d{3}-\d{3}$")
    if not CARD_RE.fullmatch(message.text):
        await message.answer("Формат карты: xxx-xxx-xxx-xxx")
        return

    await state.update_data(card_id=message.text, resident_tg_id=message.from_user.id)
    data = await state.get_data()
    try:
        if data['transaction_type'] == 'начисление':
            result = await accrue_points(
                price=int(data["price"]),
                card_id=data["card_id"],
                resident_tg_id=data["resident_tg_id"],
            )
            await message.answer(f"✅ Бонусы начислены")
        else:  # списание
            result = await deduct_points(
                price=int(data["price"]),
                card_id=data["card_id"],
                resident_tg_id=data["resident_tg_id"],
            )
            await message.answer(f"✅ Бонусы списаны")
    except ValueError as e:
        await message.answer(f"Произошла Ошибка\n{e}")
    await state.clear()

    