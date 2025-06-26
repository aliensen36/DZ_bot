import logging
import aiohttp

from data.config import config_settings
from data.url import url_loyalty

logger = logging.getLogger(__name__)


async def fetch_loyalty_card(user_id: int) -> dict:
    """
    Получает данные карты лояльности по tg_id через внешний API.
    """
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    logger.info(f"Fetching loyalty card for tg_id={user_id}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_loyalty}{user_id}/", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Successfully fetched loyalty card for tg_id={user_id}: {data}")
                    return data
                else:
                    logger.warning(f"Failed to fetch loyalty card for tg_id={user_id}, status={resp.status}")
                    return {}
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching loyalty card for tg_id={user_id}: {e}")
        return {}


async def get_user_data(user_id: int) -> dict:
    """
    Получает данные пользователя по tg_id через внешний API.
    """
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    logger.info(f"Fetching dynamic loyalty card for tg_id={user_id}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_loyalty}{user_id}/", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "user_first_name": data.get("user_first_name"),
                        "user_last_name": data.get("user_last_name"),
                        "birth_date": data.get("birth_date"),
                        "phone_number": data.get("phone_number"),
                        "email": data.get("email")
                    }
                else:
                    logger.warning(f"Failed to fetch user data for tg_id={user_id}, status={resp.status}")
                    return {}
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching user data for tg_id={user_id}: {e}")
        return {}



# async def create_loyalty_card(user_id: int):
#     """
#     Асинхронно создает карту лояльности для пользователя по его user_id.
#     Аргументы:
#         user_id (int): Идентификатор пользователя, для которого создается карта лояльности.
#     Возвращает:
#         dict: Данные созданной карты лояльности, если карта успешно создана.
#         None: Если карта уже существует для данного пользователя.
#     Вызывает:
#         RuntimeError: В случае ошибки при создании карты или при получении некорректного ответа от сервера.
#     Логирование:
#         - Информация о попытке создания карты.
#         - Информация, если карта уже существует.
#         - Предупреждение и ошибка при неудачных попытках создания карты.
#         - Исключения логируются с подробностями.
#     """
#
    # payload = {"user_id": user_id}
    # headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    # logger.info(f"Creating loyalty card for user_id={user_id}")
    #
    # try:
    #     async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
    #         async with session.post(
    #             url=url_loyalty,
    #             json=payload,
    #             headers=headers
    #         ) as resp:
    #             text = await resp.text()
    #             if resp.status == 201:
    #                 card_data = await resp.json()
    #                 logger.info(f"Loyalty card created for user_id={user_id}, status={resp.status}")
    #                 return card_data
    #             elif resp.status == 400:
    #                 if "у вас уже есть карта" in text.lower():
    #                     logger.info(f"Loyalty card already exists for user_id={user_id}")
    #                     return None
    #                 logger.warning(f"Failed to create loyalty card for user_id={user_id}: {text}")
    #                 raise RuntimeError(f"Не удалось создать карту: {text}")
    #             else:
    #                 logger.error(f"Failed to create loyalty card for user_id={user_id}: status={resp.status}, response={text}")
    #                 raise RuntimeError(f"Ошибка сервера ({resp.status}): {text}")
    # except Exception as e:
    #     logger.exception(f"Exception while creating loyalty card for user_id={user_id}: {str(e)}")
    #     raise RuntimeError(f"Произошла ошибка при создании карты: {str(e)}")