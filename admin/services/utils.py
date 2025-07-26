import aiohttp
from data.config import config_settings
from data.url import url_category, url_resident


# =================================================================================================
# API функции для работы с категориями резидентов
# =================================================================================================


async def fetch_categories() -> list[dict]:
    """Получение списка категорий из API"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url_category,
            headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
        ) as response:
            response.raise_for_status()
            return await response.json()


async def create_category(name: str) -> dict:
    """Создание новой категории через API"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url_category,
            headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
            json={"name": name}
        ) as response:
            response.raise_for_status()
            return await response.json()


async def delete_category(category_id: int) -> bool:
    """Удаление категории через API"""
    async with aiohttp.ClientSession() as session:
        async with session.delete(
            f"{url_category}{category_id}/",
            headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
        ) as response:
            return response.status == 204


# =================================================================================================
#
# =================================================================================================












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
# async def get_categories_keyboard():
#     categories = await fetch_resident_categories()
#     print(f"Categories received: {categories}")  # Отладка
#     if categories is None or not isinstance(categories, list) or not categories:
#         print("No categories or invalid format")  # Отладка
#         return None  # Возвращаем None, если нет категорий
#     builder = InlineKeyboardBuilder()
#     for category in categories:
#         try:
#             if isinstance(category, dict):
#                 builder.button(
#                     text=category.get('name', 'Unknown'),
#                     callback_data=f"category_{category.get('id', 'unknown')}"
#                 )
#             else:
#                 builder.button(text=category[1], callback_data=f"category_{category[0]}")
#         except (KeyError, IndexError) as e:
#             print(f"Error processing category {category}: {e}")
#             continue
#     builder.adjust(1)
#     markup = builder.as_markup()
#     print(f"Keyboard markup: {markup}")  # Отладка
#     return markup


# Создание новой категории резидента
async def create_new_category(category_name: str):
    """
    Создаёт новую категорию в DRF API.

    Args:
        category_name: Название категории

    Returns:
        str or None: ID новой категории (value) или None в случае ошибки
    """
    url = f"{url_category}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    payload = {"name": category_name}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                print(f"Create category status: {response.status}")
                if response.status == 201:
                    data = await response.json()
                    return data.get('id', data.get('value'))  # Возвращаем id или value
                else:
                    print(f"Error creating category: {await response.text()}")
    except aiohttp.ClientError as e:
        print(f"HTTP Client Error creating category: {e}")
    except Exception as e:
        print(f"Unexpected error creating category: {e}")
    return None

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
