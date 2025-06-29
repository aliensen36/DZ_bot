from client.services.loyalty import fetch_loyalty_card
from data.config import config_settings
from data.url import url_users, url_point_transactions_acrue, url_loyalty, url_point_transactions_deduct, url_resident
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
    url = f"{url_loyalty.rstrip('/')}/{card_number}/"
    logger.info(f"Fetching user by card_number={card_number}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Successfully fetched user by card_number={card_number}")
                    return {
                        "tg_id": data.get("tg_id"),
                        "user_first_name": data.get("user_first_name"),
                        "user_last_name": data.get("user_last_name"),
                        "phone_number": data.get("phone_number")
                    }
                else:
                    logger.warning(f"Failed to fetch user by card_number={card_number}, status={resp.status}")
                    return {}
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching user by card_number={card_number}: {e}")
        return {}

async def get_card_number_by_user(tg_id: int) -> str:
    """Получение номера карты по tg_id через API."""
    card_data = await fetch_loyalty_card(tg_id)
    if card_data and card_data.get('card_image'):
        # Предполагаем, что API возвращает номер карты или его можно извлечь
        # Если API не возвращает номер карты, нужно добавить отдельный эндпоинт
        return "123456"  # Заглушка, замените на реальный номер карты из API
    return None

async def add_points_to_card(tg_id: int, points: int) -> bool:
    """Начисление баллов через API."""
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    logger.info(f"Adding {points} points to user tg_id={tg_id}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(
                f"{config_settings.URL_LOYALTY}{tg_id}/add-points/",
                json={'points': points},
                headers=headers
            ) as resp:
                logger.info(f"Points addition response for tg_id={tg_id}: status={resp.status}")
                return resp.status == 200
    except aiohttp.ClientError as e:
        logger.error(f"Error adding points for tg_id={tg_id}: {e}")
        return False


# async def get_card_number(card_number: str) -> int:
#     async with aiohttp.ClientSession() as session:
#         async with session.get(
#             url_loyalty,
#             headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
#         ) as resp:
#             resp.raise_for_status()
#             cards: list[dict] = await resp.json()
#
#     for card in cards:
#         if card.get("card_number") == card_number:
#             return card.get('id')
#
#
#     raise ValueError("Карта не найдена!")
#
# async def get_resident_by_tg_id(resident_tg_id: int):
#     async with aiohttp.ClientSession() as session:
#         async with session.get(
#             url_users,
#             headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
#         ) as resp:
#             resp.raise_for_status()
#             users: list[dict] = await resp.json()
#     for user in users:
#         if user.get("tg_id") == resident_tg_id:
#             user = user
#             break
#
#
#
#     async with aiohttp.ClientSession() as session:
#         async with session.get(
#             url_resident,
#             headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
#         ) as resp:
#             resp.raise_for_status()
#             residents: list[dict] = await resp.json()
#     for resident in residents:
#         if resident.get("user") == user:
#             return resident.get("id")
#
#     raise ValueError("Вы не резидент!")
#
#
# async def accrue_points(
#         *,
#         price: int,
#         card_id: str,
#         resident_tg_id: int,
#     ) -> dict:
#     card_number = await get_card_number(card_number=card_id)
#     resident_id = 1 # заменть когда поменяют на бэке
#     tx_payload = {
#         "card_id": card_number,
#         "price": price,
#         "resident_id": resident_id,
#     }
#     async with aiohttp.ClientSession(
#         timeout=aiohttp.ClientTimeout(total=10),
#     ) as session:
#         async with session.post(
#             url_point_transactions_acrue,
#             json=tx_payload,
#             headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
#         ) as resp:
#             resp.raise_for_status()
#             return await resp.json()
#
# async def deduct_points(
#         *,
#         price: int,
#         card_id: str,
#         resident_tg_id: int
#     ) -> dict:
#     card_number = await get_card_number(card_number=card_id)
#     resident_id = 1  # заменят, когда появится в API
#     tx_payload = {
#         "card_id": card_number,
#         "price": price,
#         "resident_id": resident_id,
#     }
#     async with aiohttp.ClientSession(
#         timeout=aiohttp.ClientTimeout(total=10),
#     ) as session:
#         async with session.post(
#             url_point_transactions_deduct,
#             json=tx_payload,
#             headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
#         ) as resp:
#             resp.raise_for_status()
#             return await resp.json()
#
