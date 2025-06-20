import logging
import re
from datetime import datetime

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import F

from client.keyboards.inline import get_profile_inline_kb
from client.services.loyalty import fetch_loyalty_card
from client.services.user import update_user_data
from client.keyboards.reply import main_kb, edit_keyboard, edit_data_keyboard

logger = logging.getLogger(__name__)

profile_router = Router()

name_pattern = re.compile(r"^[А-Яа-яA-Za-zёЁ\-]{2,}$")
email_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$")

class EditUserData(StatesGroup):
    choosing_field = State()
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_birth_date = State()
    waiting_for_phone = State()
    waiting_for_email = State()


# Хендлер для кнопки "Личный кабинет"
@profile_router.message(F.text == "👤 Личный кабинет")
async def handle_profile(message: Message):
    """Обрабатывает запрос на открытие личного кабинета.

    Args:
        message (Message): Сообщение с нажатием кнопки "Личный кабинет".

    Notes:
        Отправляет сообщение с инлайн-клавиатурой get_profile_inline_kb.
    """
    try:
        await message.answer(
            "🔐 Ваш личный кабинет",
            reply_markup=await get_profile_inline_kb()
        )
    except Exception as e:
        logging.error(f"Error handling profile request: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка, попробуйте позже")


# Хендлер для кнопки "Мои данные"
@profile_router.callback_query(F.data == "my_data")
async def my_data_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer()

    card =  await fetch_loyalty_card(user_id)

    try:
        if not card:
            await callback.message.answer("⚠️ У вас нет активной карты лояльности.")
            return
        
        user_data_message = (
            f"👤 <b>Ваши данные:</b>\n\n"
            f"🪪 Имя: {card.get('user_first_name')}\n"
            f"🧾 Фамилия: {card.get('user_last_name')}\n"
            f"🎂 Дата рождения: {card.get('birth_date')}\n"
            f"📱 Телефон: {card.get('phone_number')}\n"
            f"📧 Email: {card.get('email')}\n\n"
        )

        await callback.message.answer(
            user_data_message,
            reply_markup=edit_keyboard,
        )

    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.debug(f"Ignored 'message not modified' for user {callback.from_user.id}")
        else:
            logging.error(f"TelegramBadRequest: {e}")
            await callback.answer()
            raise

@profile_router.message(F.text == "✏️ Изменить данные")
async def show_edit_data_menu(message: Message):
    await message.answer("Выберите, что хотите изменить:", reply_markup=edit_data_keyboard)

# Обработчик: Вернуться к основному меню
@profile_router.message(F.text == "🔙 Вернуться")
async def go_back_to_main_menu(message: Message):
    await message.answer("Вы вернулись в главное меню 👇", reply_markup=main_kb)

@profile_router.message(F.text == "✏️ Изменить имя")
async def edit_first_name(message: Message, state: FSMContext):
    await message.answer("Введите новое имя:")
    await state.set_state(EditUserData.waiting_for_first_name)

@profile_router.message(F.text == "✏️ Изменить фамилию")
async def edit_last_name(message: Message, state: FSMContext):
    await message.answer("Введите новую фамилию:") 
    await state.set_state(EditUserData.waiting_for_last_name)

@profile_router.message(F.text == "📅 Изменить дату рождения")
async def edit_birth_date(message: Message, state: FSMContext):
    await message.answer("Введите новую дату рождения (в формате ГГГГ-ММ-ДД):")
    await state.set_state(EditUserData.waiting_for_birth_date)

@profile_router.message(F.text == "📞 Изменить номер телефона")
async def edit_phone(message: Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Введите ваш номер телефона или нажмите кнопку ниже:",
        reply_markup=keyboard
    )
    await state.set_state(EditUserData.waiting_for_phone)

@profile_router.message(F.text == "📧 Изменить email")
async def edit_email(message: Message, state: FSMContext):
    await message.answer("Введите новый email:")
    await state.set_state(EditUserData.waiting_for_email)

@profile_router.message(EditUserData.waiting_for_first_name)
async def process_first_name(message: Message, state: FSMContext):
    if not name_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Имя должно содержать только буквы и быть не короче 2 символов. Попробуйте снова:")
        return
    
    await update_user_data(user_id=message.from_user.id, first_name=message.text, last_name=None, birth_date=None, phone_number=None, email=None)
    await message.answer("✅ Имя обновлено.")
    await state.clear()

@profile_router.message(EditUserData.waiting_for_last_name)
async def process_last_name(message: Message, state: FSMContext):
    if not name_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Фамилия должна содержать только буквы и быть не короче 2 символов. Попробуйте снова:")
        return

    await update_user_data(user_id=message.from_user.id, first_name=None, last_name=message.text, birth_date=None, phone_number=None, email=None)
    await message.answer("✅ Фамилия обновлена.")
    await state.clear()

@profile_router.message(EditUserData.waiting_for_birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    try:
        birth_date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        birth_date_iso = birth_date_obj.date().isoformat()
    except ValueError:
        await message.answer("⚠️ Неверный формат. Попробуйте снова (ДД.ММ.ГГГГ):")
        return
    
    await update_user_data(user_id=message.from_user.id, first_name=None, last_name=None, birth_date=birth_date_iso, phone_number=None, email=None)
    await message.answer("✅ Дата рождения обновлена.")
    await state.clear()

@profile_router.message(EditUserData.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip()

    # Удаляем пробелы, тире, скобки и прочие символы кроме цифр и плюса
    phone = re.sub(r"[^\d+]", "", phone)

    # Если начинается с 8, заменим на +7 (российская стандартизация)
    if phone.startswith("8") and len(phone) == 11:
        normalized = "+7" + phone[1:]
    elif phone.startswith("7") and len(phone) == 11:
        normalized = "+7" + phone[1:]
    elif phone.startswith("+") and 11 <= len(re.sub(r"\D", "", phone)) <= 15:
        normalized = phone
    else:
        # Невалидный формат
        await message.answer(
            "⚠️ Введите корректный номер телефона с кодом страны, например: +79001234567",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # Финальная проверка на формат
    if not re.fullmatch(r"^\+\d{11,15}$", normalized):
        await message.answer(
            "⚠️ Номер должен начинаться с + и содержать от 11 до 15 цифр. Попробуйте снова.",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    await update_user_data(user_id=message.from_user.id, first_name=None, last_name=None, birth_date=None, phone_number=message.text, email=None)
    await message.answer("✅ Номер телефона обновлён.", reply_markup=edit_data_keyboard)
    await state.clear()

@profile_router.message(EditUserData.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    if not email_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Неверный формат email. Попробуйте снова:")
        return
    
    await update_user_data(user_id=message.from_user.id, first_name=None, last_name=None, birth_date=None, phone_number=None, email=message.text)
    await message.answer("✅ Email обновлён.")
    await state.clear()

    
# Хендлер для кнопки "Мои подписки
@profile_router.callback_query(F.data == "my_subscriptions")
async def my_subscriptions_handler(callback: CallbackQuery):
    """Отображает список подписок пользователя.

    Args:
        callback (CallbackQuery): Callback-запрос от кнопки "Мои подписки".

    Notes:
        Редактирует сообщение со списком подписок.
    """
    try:
        user_data_message = (
            "🔔 <b>Ваши подписки:</b>\n\n"
            "🍕 Акции Пиццерии «Сыр-р-р»\n\n"
            "🎵 Афиша «Гластонберри»\n\n"
            "📚 Новости лектория «Обсудим»\n\n"
        )
        await callback.message.edit_text(
            user_data_message,
            reply_markup=await get_profile_inline_kb()
        )
        await callback.answer()
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.debug(f"Ignored 'message not modified' for user {callback.from_user.id}")
        else:
            logging.error(f"TelegramBadRequest: {e}")
            raise
    finally:
        await callback.answer()


# Хендлер для кнопки "Мои бонусы"
@profile_router.callback_query(F.data == "my_bonuses")
async def my_bonuses_handler(callback: CallbackQuery):
    """Отображает доступные бонусы пользователя.

    Args:
        callback (CallbackQuery): Callback-запрос от кнопки "Мои бонусы".

    Notes:
        Редактирует сообщение со списком бонусов.
    """
    try:
        user_data_message = (
            "🎁 <b>Ваши бонусы</b>\n\n"
            "☕ <b>15% скидка</b> на кофе в «Кофеин»\n"
            "(действительна до 31.12.2025)\n\n"
            "💪 <b>1 бесплатное посещение</b> фитнес-клуба «Жми»\n"
            "(использовать до 15.11.2025)\n\n"
        )
        await callback.message.edit_text(
            user_data_message,
            reply_markup=await get_profile_inline_kb()
        )
        await callback.answer()
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logging.debug(f"Ignored 'message not modified' for user {callback.from_user.id}")
        else:
            logging.error(f"TelegramBadRequest: {e}")
            raise
    finally:
        await callback.answer()
