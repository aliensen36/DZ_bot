from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

async def get_profile_inline_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="📋 Мои данные",
                             callback_data="my_data"),
        InlineKeyboardButton(text="🔔 Мои подписки",
                             callback_data="my_subscriptions"),
        InlineKeyboardButton(text="🎁 Мои бонусы",
                             callback_data="my_bonuses"),
        InlineKeyboardButton(text="🔍 Сканировать QR-код", 
                             callback_data="scanqr"),
        ]
    builder.add(*buttons)
    builder.adjust(1)

    return builder.as_markup()


