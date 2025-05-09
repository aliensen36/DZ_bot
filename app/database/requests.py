import logging

from tortoise.exceptions import DoesNotExist
from app.database.models import User


logger = logging.getLogger(__name__)


# ----- ПОЛЬЗОВАТЕЛЬ -----------
async def create_user(tg_id: int):  # создание пользователя
    user = await User.get_or_create(tg_id=tg_id)
    return