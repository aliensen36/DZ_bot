import logging
from datetime import datetime
from typing import Optional

import aiogram
from tortoise.exceptions import IntegrityError

from database.models import User, Mailing

logger = logging.getLogger(__name__)

class UserRequests:
    @staticmethod
    async def get_or_create_from_telegram(tg_user: 'aiogram.types.User') -> User:
        """Создает или обновляет пользователя из объекта Telegram"""
        first_name = tg_user.first_name or "Unknown"
        last_name = tg_user.last_name
        username = tg_user.username

        try:
            user, created = await User.get_or_create(
                tg_id=tg_user.id,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'username': username,
                    'is_bot': tg_user.is_bot,
                }
            )

            if not created:
                update_data = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'username': username,
                    'last_activity': datetime.now()
                }

                needs_update = any(
                    getattr(user, field) != value
                    for field, value in update_data.items()
                )

                if needs_update:
                    for field, value in update_data.items():
                        setattr(user, field, value)
                    await user.save(update_fields=list(update_data.keys()))

            return user

        except IntegrityError as e:
            logger.error(f"Integrity error for user {tg_user.id}: {e}")
            user = await User.get(tg_id=tg_user.id)
            await user.save()
            return user

    @staticmethod
    async def create_simple_user(tg_id: int) -> User:
        """Создает пользователя с минимальными данными"""
        return await User.create(tg_id=tg_id, first_name="Unknown")

    @staticmethod
    async def update_activity(tg_id: int) -> None:
        """Обновляет время последней активности"""
        await User.filter(tg_id=tg_id).update(last_activity=datetime.now())

    @staticmethod
    async def get_by_tg_id(tg_id: int) -> Optional[User]:
        """Получает пользователя по telegram ID"""
        return await User.get_or_none(tg_id=tg_id)
    
    @staticmethod
    async def get_all_users() -> list[User]:
        """Получает всех пользователей"""
        return await User.all()

class MailingRequests:
    @staticmethod
    async def create_mailing(from_user: User, text: str, image: Optional[str] = None, button_url: Optional[str] = None, type: Optional[str] = "other") -> Mailing:
        """Создает рассылку"""
        return await Mailing.create(
            from_user=from_user,
            text=text,
            image=image,
            button_url=button_url
        )