from data.config import config_settings
from data.url import url_users, url_point_transactions_acrue
import aiohttp
from data.url import base_url


async def get_resident_id(resident_tg_id: str) -> int:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url_users,
            headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
        ) as resp:
            resp.raise_for_status()
            users: list[dict] = await resp.json()

    for user in users:
        if user.get("tg_id") == resident_tg_id:      # ← твой критерий поиска
            return user["id"]

    raise ValueError("Resident not found")


async def accrue_points(
        *,
        price: int,
        card_id: str,
        resident_tg_id: int,
    ) -> dict:
    resident_id = await get_resident_id(resident_tg_id=resident_tg_id)
    tx_payload = {
        "card_id": card_id,
        "price": price,
        "resident_id": resident_id,
    }

    async with aiohttp.ClientSession(
        base_url=base_url,
        timeout=aiohttp.ClientTimeout(total=10),
    ) as session:
        async with session.post(
            url_point_transactions_acrue,
            params={"card_id": card_id, "price": price, "resident_id": resident_id},
            json=tx_payload,
            headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
        ) as resp:
            resp.raise_for_status()
            return await resp.json()