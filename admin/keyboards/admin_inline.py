import aiohttp
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup
from aiogram.types import InlineKeyboardButton
from data.config import config_settings
from data.url import url_resident, url_category


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
        List[Tuple[str, str]]: Список категорий в формате [(value, name), ...]
        None: В случае ошибки
    """
    url = f"{url_category}"
    headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
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
    print(f"Categories received: {categories}")  # Отладка
    if categories is None or not isinstance(categories, list) or not categories:
        print("No categories or invalid format")  # Отладка
        return None  # Возвращаем None, если нет категорий
    builder = InlineKeyboardBuilder()
    for category in categories:
        try:
            if isinstance(category, dict):
                builder.button(
                    text=category.get('name', 'Unknown'),
                    callback_data=f"category_{category.get('id', 'unknown')}"
                )
            else:
                builder.button(text=category[1], callback_data=f"category_{category[0]}")
        except (KeyError, IndexError) as e:
            print(f"Error processing category {category}: {e}")
            continue
    builder.adjust(1)
    markup = builder.as_markup()
    print(f"Keyboard markup: {markup}")  # Отладка
    return markup


# Функция для создания инлайн-клавиатуры отмены
def inline_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])