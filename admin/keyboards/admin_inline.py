import aiohttp
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup
from aiogram.types import InlineKeyboardButton
from data.config import config_settings
from data.url import url_resident, url_category


# =================================================================================================
# Для рассылок
# =================================================================================================

async def mailing_keyboard(message_size: int) -> InlineKeyboardBuilder:
    """Создаёт инлайн-клавиатуру для управления рассылкой.

    Args:
        message_size (int): Размер текста рассылки в символах.

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками для добавления картинки, ссылки, отмены, изменения текста и отправки.

    Notes:
        Кнопка "Добавить картинку" доступна только если message_size <= 1024.
    """
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
    """Создаёт инлайн-клавиатуру с кнопкой для перехода по ссылке.

    Args:
        link (str): URL для кнопки "Перейти".

    Returns:
        InlineKeyboardMarkup: Клавиатура с одной кнопкой "Перейти".
    """
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


# =================================================================================================
# Для категорий резидентов
# =================================================================================================


def get_categories_keyboard():
    """Клавиатура для управления категориями"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить категорию", callback_data="add_category")
    builder.button(text="Удалить категорию", callback_data="delete_category_menu")
    builder.button(text="Назад", callback_data="back_to_residents_management")
    builder.adjust(1)
    return builder.as_markup()


def get_delete_categories_keyboard(categories):
    """Клавиатура для выбора категории на удаление"""
    builder = InlineKeyboardBuilder()

    for category in categories:
        builder.button(
            text=f"❌ {category['name']}",
            callback_data=f"confirm_delete_category_{category['id']}"
        )

    builder.button(text="Отмена", callback_data="cancel_delete_category")
    builder.adjust(1)
    return builder.as_markup()


def get_confirmation_keyboard(category_id):
    """Клавиатура подтверждения удаления"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, удалить", callback_data=f"delete_category_{category_id}")
    builder.button(text="Отмена", callback_data="cancel_delete_category")
    builder.adjust(2)
    return builder.as_markup()


# =================================================================================================
# Для резидентов
# =================================================================================================


def residents_management_inline_keyboard() -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для управления резидентами"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗂 Категории резидентов", callback_data="resident_categories")],
            [InlineKeyboardButton(text="📋 Резиденты", callback_data="residents_list")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ]
    )
    return keyboard






# Функция для создания инлайн-клавиатуры отмены
def inline_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])





























