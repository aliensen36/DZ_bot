from client.services.loyalty import fetch_loyalty_card
from data.config import config_settings
from data.url import url_users, url_loyalty, url_point_transactions_deduct, url_resident
import aiohttp

import logging
logger = logging.getLogger(__name__)


async def find_user_by_phone(phone_number: str) -> dict:
    """Поиск пользователя по номеру телефона через API."""
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    # Нормализуем номер телефона
    phone_number_clean = ''.join(filter(str.isdigit, phone_number))
    phone_variants = [phone_number_clean]
    if phone_number_clean.startswith('8'):
        phone_variants.append(f"+7{phone_number_clean[1:]}")
    elif phone_number_clean.startswith('7'):
        phone_variants.append(f"+{phone_number_clean}")

    for variant in phone_variants:
        url = f"{url_users}phone/{variant}/"
        logger.info(f"Fetching user by phone_number={variant}, URL={url}")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Successfully fetched user by phone_number={variant}: {data}")
                        return {
                            "tg_id": data.get("tg_id"),
                            "user_first_name": data.get("user_first_name"),
                            "user_last_name": data.get("user_last_name"),
                            "phone_number": data.get("phone_number")
                        }
                    else:
                        logger.warning(f"Failed to fetch user by phone_number={variant}, status={resp.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Error fetching user by phone_number={variant}: {e}")

    logger.warning(f"No user found for phone_number={phone_number} in any format")
    return {}


async def find_user_by_card_number(card_number: str) -> dict:
    """Поиск пользователя по номеру карты через API."""
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    # Форматируем номер карты для соответствия формату "123 456"
    card_number_clean = f"{card_number[:3]} {card_number[3:]}"
    url = f"{url_loyalty}card-number/{card_number_clean}/"
    logger.info(f"Fetching user by card_number={card_number_clean}, URL={url}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Successfully fetched user by card_number={card_number_clean}")
                    return {
                        "tg_id": data.get("tg_id"),
                        "user_first_name": data.get("user_first_name"),
                        "user_last_name": data.get("user_last_name"),
                        "phone_number": data.get("phone_number")
                    }
                else:
                    logger.warning(f"Failed to fetch user by card_number={card_number_clean}, status={resp.status}")
                    return {}
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching user by card_number={card_number_clean}: {e}")
        return {}

async def get_card_number_by_user(tg_id: int) -> str | None:
    """Получение номера карты по tg_id через API."""
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    url = f"{url_loyalty}{tg_id}/card-number/"

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    card_number = data.get('card_number')
                    logger.info(f"Successfully fetched card_number={card_number} for tg_id={tg_id}")
                    return card_number
                else:
                    logger.warning(f"Failed to fetch card number for tg_id={tg_id}, status={resp.status}")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching card number for tg_id={tg_id}: {e}")
        return None


async def get_card_id_by_tg_id(tg_id: int) -> int | None:
    """Получение ID карты по tg_id через API."""
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    url = f"{url_loyalty}{tg_id}/card-id/"

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    card_id = data.get('card_id')
                    logger.info(f"Successfully fetched card_id={card_id} for tg_id={tg_id}")
                    return card_id
                else:
                    logger.warning(f"Failed to fetch card_id for tg_id={tg_id}, status={resp.status}")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching card_id for tg_id={tg_id}: {e}")
        return None


async def get_resident_id_by_user_id(user_id: int) -> int | None:
    """Получение resident_id по user_id через API."""
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_resident}?user={user_id}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        resident_id = data[0].get('id')
                        logger.info(f"Successfully fetched resident_id={resident_id} for user_id={user_id}")
                        return resident_id
                    else:
                        logger.warning(f"No resident found for user_id={user_id}")
                        return None
                else:
                    logger.warning(f"Failed to fetch resident_id for user_id={user_id}, status={resp.status}")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching resident_id for user_id={user_id}: {e}")
        return None


async def get_user_id_by_tg_id(tg_id: int) -> int | None:
    """Получение user_id по tg_id через API."""
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_users}?tg_id={tg_id}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        user_id = data[0].get('id')
                        logger.info(f"Successfully fetched user_id={user_id} for tg_id={tg_id}")
                        return user_id
                    else:
                        logger.warning(f"No user found for tg_id={tg_id}")
                        return None
                else:
                    logger.warning(f"Failed to fetch user_id for tg_id={tg_id}, status={resp.status}")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching user_id for tg_id={tg_id}: {e}")
        return None
