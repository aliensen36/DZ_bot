import aiohttp

from data.config import config_settings
from data.url import url_subscription


async def get_my_subscriptions(tg_id: int) -> list[str]:
    """
    Асинхронно получает список подписок пользователя по его Telegram ID.
    Аргументы:
        tg_id (int): Идентификатор пользователя Telegram.
    Возвращает:
        list[str]: Список названий подписок пользователя. В случае ошибки возвращает пустой список.
    Исключения:
        aiohttp.ClientResponseError: В случае ошибки HTTP-запроса.
        Exception: В случае других ошибок при выполнении запроса.
    """

    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(
                url=f"{url_subscription}my/",
                headers=headers,
                params={"tg_id": str(tg_id)}
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return [item["name"] for item in data if "name" in item]
    except aiohttp.ClientResponseError as e:
        print(f"Сбой при получении подписок: HTTP {e.status}, message='{e.message}', url='{e.request_info.url}'")
        return []
    except Exception as e:
        print(f"Сбой при получении подписок: {e}")
        return []
    

async def get_subscriptions_name():
    """
    Асинхронно получает список названий подписок с удалённого сервера.
    Возвращает:
        list[str]: Список названий подписок, если запрос успешен, иначе пустой список.
    Исключения:
        В случае ошибки при выполнении запроса или обработке данных функция выводит сообщение об ошибке и возвращает пустой список.
    """

    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url=url_subscription, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                return [item["name"] for item in data if "name" in item]

    except Exception as e:
        print(f"Ошибка при получении подписок: {e}")
        return []
    

async def get_subscriptions_data():
    """
    Асинхронно получает данные о подписках с внешнего сервиса.
    Возвращает:
        list или dict: Данные о подписках в формате JSON, полученные от внешнего API.
        В случае ошибки возвращает пустой список.
    Исключения:
        Все исключения обрабатываются внутри функции, ошибки выводятся в консоль.
    """

    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url=url_subscription, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
    except Exception as e:
        print(f"Ошибка при получении списка подписок: {e}")
        return []