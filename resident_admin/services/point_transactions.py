from data.config import config_settings
from data.url import url_users, url_point_transactions_acrue, url_loyalty, url_point_transactions_deduct, url_resident
import aiohttp


async def get_card_number(card_number: str) -> int:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url_loyalty,
            headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
        ) as resp:
            resp.raise_for_status()
            cards: list[dict] = await resp.json()
            
    for card in cards:
        if card.get("card_number") == card_number:
            return card.get('id')
    

    raise ValueError("Карта не найдена!")

async def get_resident_by_tg_id(resident_tg_id: int):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url_users,
            headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
        ) as resp:
            resp.raise_for_status()
            users: list[dict] = await resp.json()
    for user in users:
        if user.get("tg_id") == resident_tg_id:   
            user = user
            break
    
    
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url_resident,
            headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
        ) as resp:
            resp.raise_for_status()
            residents: list[dict] = await resp.json()
    for resident in residents:
        if resident.get("user") == user:   
            return resident.get("id")
    
    raise ValueError("Вы не резидент!")
    

async def accrue_points(
        *,
        price: int,
        card_id: str,
        resident_tg_id: int,
    ) -> dict:
    card_number = await get_card_number(card_number=card_id)
    resident_id = 1 # заменть когда поменяют на бэке
    tx_payload = {
        "card_id": card_number,
        "price": price,
        "resident_id": resident_id,
    }
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10),
    ) as session:
        async with session.post(
            url_point_transactions_acrue,
            json=tx_payload,
            headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
        
async def deduct_points(
        *, 
        price: int,          
        card_id: str,        
        resident_tg_id: int  
    ) -> dict:
    card_number = await get_card_number(card_number=card_id)   
    resident_id = 1  # заменят, когда появится в API
    tx_payload = {
        "card_id": card_number,
        "price": price,
        "resident_id": resident_id,
    }
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10),
    ) as session:
        async with session.post(
            url_point_transactions_deduct,
            json=tx_payload,
            headers={"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()},
        ) as resp:
            resp.raise_for_status()
            return await resp.json()
            
