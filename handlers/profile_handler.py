from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram import F

from keyboards.inline import get_profile_inline_kb

profile_router = Router()

@profile_router.message(F.text == "Личный кабинет")
async def handle_profile(message: Message):
    await message.answer(
        "🔐 Ваш личный кабинет",
        reply_markup=await get_profile_inline_kb()
    )


# Хендлер для кнопки "Мои данные"
@profile_router.callback_query(F.data == "my_data")
async def my_data_handler(callback: CallbackQuery):
    user_data_message = (
        "📋 <b>Ваши данные:</b>\n\n"
        "Фамилия, имя: <i>Иванов Иван</i>\n\n"
        "Дата рождения: <i>01.01.2001</i>"
    )
    await callback.message.edit_text(
        user_data_message,
        reply_markup=await get_profile_inline_kb()
    )
    await callback.answer()

# Хендлер для кнопки "Мои данные"
@profile_router.callback_query(F.data == "my_data")
async def my_data_handler(callback: CallbackQuery):
    user_data_message = (
        "📋 <b>Ваши данные:</b>\n\n"
        "Фамилия, имя: <i>Иванов Иван</i>\n\n"
        "Дата рождения: <i>01.01.2001</i>"
    )
    await callback.message.edit_text(
        user_data_message,
        reply_markup=await get_profile_inline_kb()
    )
    await callback.answer()

    # Хендлер для кнопки "Мои подписки
@profile_router.callback_query(F.data == "my_subscriptions")
async def my_data_handler(callback: CallbackQuery):
    user_data_message = (
        "📋 <b>Ваши Подписки:</b>\n\n"
        "Подписка: <i>ААА</i>\n\n"
        "Подписка: <i>БББ</i>"
    )
    await callback.message.edit_text(
        user_data_message,
        reply_markup=await get_profile_inline_kb()
    )
    await callback.answer()

    # Хендлер для кнопки "Мои Бонусы"
@profile_router.callback_query(F.data == "my_bonuses")
async def my_data_handler(callback: CallbackQuery):
    user_data_message = (
        "📋 <b>Ваши Бонусы:</b>\n\n"
        "На посещение XXX: <i>100 Балов</i>\n\n"
        "На посещение YYY: <i>305 Балов</i>"
    )
    await callback.message.edit_text(
        user_data_message,
        reply_markup=await get_profile_inline_kb()
    )
    await callback.answer()