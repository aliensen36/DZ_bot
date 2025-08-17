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
    """Клавиатура управления категориями"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить категорию", callback_data="add_category")
    builder.button(text="🗑 Удалить категорию", callback_data="delete_category_menu")
    builder.button(text="↩️ Назад", callback_data="back_to_residents_management")
    builder.adjust(1)
    return builder.as_markup()


def get_delete_categories_keyboard(categories: list[dict]) -> InlineKeyboardBuilder:
    """Создает клавиатуру для удаления категорий"""
    builder = InlineKeyboardBuilder()

    # Собираем все ID подкатегорий
    subcategory_ids = set()

    def collect_child_ids(cat):
        for child in cat.get('children', []):
            subcategory_ids.add(child['id'])
            collect_child_ids(child)

    for cat in categories:
        collect_child_ids(cat)

    def add_category_buttons(cats, level=0):
        for cat in cats:
            # Пропускаем подкатегории в основном списке
            if level == 0 and cat['id'] in subcategory_ids:
                continue

            # Добавляем кнопку категории
            btn_text = "    " * level + ("- подкатегория:  " if level > 0 else "") + cat['name']
            builder.button(
                text=btn_text,
                callback_data=f"confirm_delete_category_{cat['id']}"
            )

            # Рекурсивно добавляем дочерние категории
            if cat.get('children'):
                add_category_buttons(cat['children'], level + 1)

    add_category_buttons(categories)
    return builder


def get_confirmation_keyboard(category_id: int):
    """Клавиатура подтверждения удаления"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Да, удалить",
        callback_data=f"delete_category_{category_id}"
    )
    builder.button(
        text="❌ Отмена",
        callback_data="cancel_delete_category"
    )
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


def get_residents_management_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для управления резидентами
    со списком резидентов в качестве первой кнопки

    Returns:
        types.InlineKeyboardMarkup: Клавиатура с кнопками управления
    """
    builder = InlineKeyboardBuilder()

    # Первая строка - основная кнопка просмотра списка
    builder.row(
        InlineKeyboardButton(
            text="📋 Список резидентов",
            callback_data="show_residents_list"
        )
    )

    # Вторая строка - кнопки добавления и редактирования
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить резидента",
            callback_data="add_resident"
        ),
        InlineKeyboardButton(
            text="✏️ Изменить резидента",
            callback_data="edit_resident_list"
        )
    )

    # Третья строка - кнопки удаления и возврата
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить резидента",
            callback_data="delete_resident_list"
        ),
        InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="admin_back"
        )
    )

    return builder.as_markup()


# Функция для создания инлайн-клавиатуры отмены
def inline_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])





























