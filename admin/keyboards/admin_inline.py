import aiohttp
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup
from aiogram.types import InlineKeyboardButton
from data.config import config_settings
from data.url import url_resident


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


async def fetch_resident_categories():
    """
    Получает список категорий резидентов из DRF API

    Returns:
        List[Tuple[str, str]]: Список категорий в формате [(value, label), ...]
        None: В случае ошибки
    """
    url = f"{url_resident}categories/"
    headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('categories')
                else:
                    response.raise_for_status()
    except aiohttp.ClientError as e:
        print(f"HTTP Client Error fetching categories: {e}")
    except Exception as e:
        print(f"Unexpected error fetching categories: {e}")
    return None


# Клавиатура для выбора категории резидента
async def get_categories_keyboard():
    categories = await fetch_resident_categories()
    builder = InlineKeyboardBuilder()
    for category in categories:
        # Обрабатываем разные возможные форматы ответа
        if isinstance(category, dict):  # Если API возвращает {'value':..., 'label':...}
            builder.button(text=category['label'], callback_data=f"category_{category['value']}")
        else:  # Если API возвращает кортежи (value, label)
            builder.button(text=category[1], callback_data=f"category_{category[0]}")
    builder.adjust(1)
    return builder.as_markup()

