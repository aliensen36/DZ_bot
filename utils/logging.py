from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery
import logging

logger = logging.getLogger(__name__)  # Используем __name__ для соответствия модулю utils.logging

class CallbackLoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, CallbackQuery):
            # Получаем состояние, если оно существует
            state = await data.get('state').get_state() if data.get('state') else None
            logger.debug(f"Received callback_query: id={event.id}, data={event.data}, user_id={event.from_user.id}, state={state}")
        return await handler(event, data)