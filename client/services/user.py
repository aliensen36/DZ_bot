import logging
import aiohttp
from typing import Optional

from data.config import config_settings
from data.url import url_users

logger = logging.getLogger(__name__)


async def update_user_data(
    user_id: int,
    first_name: Optional[str],
    last_name: Optional[str],
    birth_date: Optional[str],
    phone_number: Optional[str],
    email: Optional[str]
) -> bool:
    """
    Обновляет данные пользователя по заданному идентификатору.
    Аргументы:
        user_id (int): Идентификатор пользователя.
        first_name (str): Имя пользователя.
        last_name (str): Фамилия пользователя.
        birth_date (str): Дата рождения пользователя в формате строки.
        phone_number (str): Номер телефона пользователя.
        email (str): Электронная почта пользователя.
    Возвращает:
        bool: True, если данные пользователя успешно обновлены, иначе False.
    Исключения:
        Логирует и возвращает False при возникновении ошибок клиента или других исключений.
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
        # Получаем текущие данные пользователя
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp_get:
                if resp_get.status != 200:
                    logger.error(f"Failed to fetch current user data for user_id={user_id}: status={resp_get.status}")
                    return False
                current_data = await resp_get.json()

                # Сравниваем текущие данные с payload
                update_needed = False
                for key, value in payload.items():
                    if current_data.get(key) != value:
                        update_needed = True
                        break

                if not update_needed:
                    logger.info(f"No changes needed for user_id={user_id}")
                    return True

                # Выполняем обновление только если есть изменения
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
        logger.exception(f"Unexpected error while updating user_data for user_id={user_id}: {str(e)}")
        return False