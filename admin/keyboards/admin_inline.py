from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup
from aiogram.types import InlineKeyboardButton

async def mailing_keyboard(message_size: int) -> InlineKeyboardBuilder:
    """Создание инлайн-клавиатуры для рассылки"""
    keyboard = InlineKeyboardBuilder()
    
    if message_size <= 1024:
        keyboard.add(
            InlineKeyboardButton(text="Добавить картинку",
                                 callback_data="mailing_add_image"),
        )
    
    keyboard.add(
        InlineKeyboardButton(text="Добавить ссылку для кнопки",
                             callback_data="mailing_add_button_url"),
        InlineKeyboardButton(text="Отменить рассылку",
                             callback_data="cancel_send_mailing"),
        InlineKeyboardButton(text="Изменить текст",
                             callback_data="change_text_mailing"),
        InlineKeyboardButton(text="Отправить",
                             callback_data="send_mailing"),
    )
    keyboard.adjust(2)
    return keyboard.as_markup()

async def admin_link_keyboard(link: str) -> InlineKeyboardBuilder:
    """Создание инлайн-клавиатуры для админов"""
    keyboard = InlineKeyboardBuilder()
    keyboard.add( InlineKeyboardButton(text="Перейти", url=link))
    return keyboard.as_markup()
    
accept_mailing_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить рассылку",
                              callback_data="accept_send_mailing")],
        [InlineKeyboardButton(text="Отменить рассылку",
                              callback_data="cancel_send_mailing")],
    ]
)
