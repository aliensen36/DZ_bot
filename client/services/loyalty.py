import logging
import aiohttp

from data.config import config_settings
from data.url import url_loyalty

logger = logging.getLogger(__name__)

async def fetch_loyalty_card(user_id: int):
    """Получает данные карты лояльности пользователя по его ID.

    Args:
        user_id (int): ID пользователя в Telegram.

    Returns:
        dict: Данные карты или None, если карта не найдена.

    Raises:
        RuntimeError: Если произошла ошибка при запросе.
    """
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    logger.info(f"Fetching loyalty card for user_id={user_id}")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_loyalty}{user_id}/", headers=headers) as resp:
                if resp.status == 200:
                    card_data = await resp.json()
                    logger.info(f"Loyalty card fetched for user_id={user_id}")
                    return card_data
                elif resp.status == 404:
                    logger.info(f"No loyalty card found for user_id={user_id}")
                    return None
                else:
                    text = await resp.text()
                    logger.error(f"Failed to fetch loyalty card for user_id={user_id}: status={resp.status}, response={text}")
                    return None
    except Exception as e:
        logger.exception(f"Exception while fetching loyalty card for user_id={user_id}: {str(e)}")
        return None
