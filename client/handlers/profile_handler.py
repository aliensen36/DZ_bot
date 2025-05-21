import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery
from aiogram import F

from client.keyboards.inline import get_profile_inline_kb


profile_router = Router()


# Хендлер для кнопки "Личный кабинет"
@profile_router.message(F.text == "👤 Личный кабинет")
async def handle_profile(message: Message):
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
    try:
        user_data_message = (
            "🪪 <b>Основные данные:</b>\n\n"
            "└ 🔖 <i>ФИ:</i> <code>Иванов Иван</code>\n"
            "└ 🎂 <i>Дата рождения:</i> <code>01.01.2001</code>\n\n"
            "📊 <b>Статистика:</b>\n\n"
            "└ ⏱ <i>В системе:</i> <code>2 года 3 месяца</code>\n"
            "└ 💫 <i>Последний вход:</i> <code>сегодня в 14:30</code>\n\n"
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


# Хендлер для кнопки "Мои подписки
@profile_router.callback_query(F.data == "my_subscriptions")
async def my_subscriptions_handler(callback: CallbackQuery):
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
