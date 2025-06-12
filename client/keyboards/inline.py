from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

async def get_profile_inline_kb() -> InlineKeyboardMarkup:
    """Создаёт инлайн-клавиатуру для личного кабинета.

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками "Мои данные", "Мои подписки", "Мои бонусы".

    Notes:
        Кнопки привязаны к callback_data: "my_data", "my_subscriptions", "my_bonuses".
    """
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="📋 Мои данные",
                             callback_data="my_data"),
        InlineKeyboardButton(text="🔔 Мои подписки",
                             callback_data="my_subscriptions"),
        InlineKeyboardButton(text="🎁 Мои бонусы",
                             callback_data="my_bonuses")
        ]
    builder.add(*buttons)
    builder.adjust(1)

    return builder.as_markup()



