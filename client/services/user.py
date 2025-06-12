import logging
import aiohttp

from data.config import config_settings
from data.url import url_users

logger = logging.getLogger(__name__)

async def update_user_data(user_id: int, first_name: str, last_name: str, birth_date: str, phone_number: str,
                           email: str):
    """
    Обновление данных пользователя для карты лояльности
    """
    payload = {}

    if first_name is not None:
        payload["user_first_name"] = first_name
    if last_name is not None:
        payload["user_last_name"] = last_name
    if birth_date is not None:
        payload["birth_date"] = birth_date
    if phone_number is not None:
        payload["phone_number"] = phone_number
    if email is not None:
        payload["email"] = email
        
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    url = f"{url_users.rstrip('/')}/{user_id}/"
    logger.info(f"Updating user data for user_id={user_id} with payload={payload}, url={url}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.patch(url, json=payload, headers=headers) as resp:
                response_text = await resp.text()
                if resp.status in [200, 201]:
                    logger.info(f"User data updated for user_id={user_id}, status={resp.status}")
                    return True
                else:
                    logger.error(
                        f"Failed to update user data for user_id={user_id}: status={resp.status}, response={response_text}")
                    return False
    except aiohttp.ClientError as e:
        logger.exception(f"Client error while updating user data for user_id={user_id}: {str(e)}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error while updating user data for user_id={user_id}: {str(e)}")
        return False