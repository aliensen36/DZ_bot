import aiohttp
from data.config import config_settings
from data.url import url_category, url_resident


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
