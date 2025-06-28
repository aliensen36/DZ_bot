import logging
import aiohttp

from data.config import config_settings
from data.url import url_loyalty, url_users

logger = logging.getLogger(__name__)


async def fetch_loyalty_card(user_id: int) -> dict:
    """
    Получает изображение карты лояльности по tg_id через внешний API.
    """
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    logger.info(f"Fetching loyalty card image for tg_id={user_id}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_loyalty}{user_id}/card-image/", headers=headers) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    logger.info(f"Successfully fetched loyalty card image for tg_id={user_id}")
                    return {"card_image": img_bytes}
                else:
                    logger.warning(f"Failed to fetch loyalty card image for tg_id={user_id}, status={resp.status}")
                    return {}
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching loyalty card image for tg_id={user_id}: {e}")
        return {}


async def get_user_data(user_id: int) -> dict:
    """
    Получает данные пользователя по tg_id через внешний API.
    """
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    logger.info(f"Fetching user data for tg_id={user_id}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_users}{user_id}/", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Successfully fetched user data for tg_id={user_id}")
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