import aiohttp
from aiogram.types import InlineKeyboardMarkup

from data.config import config_settings
from data.url import url_category, url_resident
from typing import Optional

import logging
logger = logging.getLogger(__name__)



# =================================================================================================
# Для работы с категориями резидентов
# =================================================================================================


async def fetch_categories(tree: bool = False) -> list[dict]:
    """Получение списка категорий из API"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
                f"{url_category}?tree={'true' if tree else 'false'}",
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
        ) as response:
            response.raise_for_status()
            return await response.json()


async def create_category(name: str, parent_id: Optional[int] = None) -> dict:
    """Создание новой категории через API"""
    async with aiohttp.ClientSession() as session:
        data = {"name": name}
        if parent_id:
            data["parent"] = parent_id

        async with session.post(
                url_category,
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
                json=data
        ) as response:
            response.raise_for_status()
            return await response.json()


async def delete_category(category_id: int) -> bool:
    """Удаление категории через API"""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(
                f"{url_category}{category_id}/",
                headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
            ) as response:
                if response.status == 404:
                    logger.error(f"Категория с ID {category_id} не найдена")
                    return False
                response.raise_for_status()
                return response.status == 204
        except Exception as e:
            logger.error(f"Ошибка при удалении категории {category_id}: {str(e)}")
            return False


async def format_categories_list(categories: list) -> str:
    """Форматирует список категорий в едином стиле"""
    if not categories:
        return "📋 Список категорий пуст."

    # Собираем все ID подкатегорий
    subcategory_ids = set()

    def collect_child_ids(cat):
        for child in cat.get('children', []):
            subcategory_ids.add(child['id'])
            collect_child_ids(child)

    for cat in categories:
        collect_child_ids(cat)

    def format_category(cat, level=0):
        # Пропускаем подкатегории при основном выводе
        if level == 0 and cat['id'] in subcategory_ids:
            return ""

        if level == 0:
            prefix = "\n\n" if not cat.get('is_first', False) else ""
            name = f"<b>{cat['name']}</b>"
        else:
            prefix = "    " * level
            name = f" - {cat['name']}"

        children = "\n".join([format_category(child, level + 1) for child in cat.get('children', [])])
        return f"{prefix}{name}{f'\n{children}' if children else ''}"

    if categories:
        categories[0]['is_first'] = True

    categories_list = "".join([format_category(cat) for cat in categories])
    return f"📋 <b>Список категорий резидентов</b>\n\n{categories_list.strip()}"


async def show_categories_message(chat_id: int, bot, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Показывает сообщение со списком категорий в едином стиле"""
    categories = await fetch_categories(tree=True)
    text = await format_categories_list(categories)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup
    )


# =================================================================================================
#
# =================================================================================================







# Создание нового резидента
async def create_new_resident(name: str, category_id: str, description: str):
    """
    Создаёт нового резидента в DRF API.

    Args:
        name: Имя резидента
        category_id: ID категории (строка или число)
        description: Описание резидента

    Returns:
        dict or None: Данные созданного резидента или None в случае ошибки
    """
    url = f"{url_resident}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    payload = {
        "name": name,
        "category_ids": [int(category_id)],  # Отправляем как список ID
        "description": description
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                print(f"Create resident status: {response.status}")
                print(f"Payload sent: {payload}")  # Отладка
                if response.status == 201:
                    return await response.json()
                else:
                    print(f"Error creating resident: {await response.text()}")
    except aiohttp.ClientError as e:
        print(f"HTTP Client Error creating resident: {e}")
    except Exception as e:
        print(f"Unexpected error creating resident: {e}")
    return None
