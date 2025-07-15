from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
import aiohttp
import logging
from data.config import config_settings
from data.url import url_promotions
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

# Роутер для админских действий
admin_promotion_router = Router()
admin_promotion_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([ADMIN_CHAT_ID], show_message=False)
)

async def update_promotion_approval(promotion_id: int, approve: bool) -> bool:
    """
    Обновляет статус подтверждения акции через API.
    """
    endpoint = "approve" if approve else "reject"
    url = f"{url_promotions}{promotion_id}/{endpoint}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as resp:
                logger.debug(f"Запрос на {endpoint} для акции {promotion_id}: status={resp.status}")
                if resp.status in (200, 204):
                    logger.info(f"Акция {promotion_id} {'подтверждена' if approve else 'отклонена'} успешно")
                    return True
                else:
                    logger.error(f"Ошибка при {'подтверждении' if approve else 'отклонении'} акции {promotion_id}: status={resp.status}, response={await resp.text()}")
                    return False
    except aiohttp.ClientError as e:
        logger.error(f"Ошибка при {'подтверждении' if approve else 'отклонении'} акции {promotion_id}: {e}")
        return False

@admin_promotion_router.callback_query(F.data.startswith("approve_promotion:"))
async def handle_approve_promotion(callback: CallbackQuery):
    """
    Обрабатывает нажатие кнопки "Подтвердить" для акции.
    """
    logger.debug(f"Получен CallbackQuery: data={callback.data}, user_id={callback.from_user.id}, message_type={callback.message.content_type}")
    
    try:
        # Извлекаем ID акции из callback_data
        promotion_id = int(callback.data.split(":")[1])
        
        # Обновляем статус акции через API
        success = await update_promotion_approval(promotion_id, approve=True)
        
        # Формируем текст ответа
        text = f"Акция с ID {promotion_id} подтверждена!" if success else f"Ошибка при подтверждении акции с ID {promotion_id}."
        
        # Проверяем тип сообщения
        try:
            if callback.message.content_type == 'photo':
                # Редактируем подпись фото
                await callback.message.edit_caption(
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])  # Пустая разметка для удаления кнопок
                )
                logger.debug(f"Edited caption for photo message {callback.message.message_id}")
            else:
                # Редактируем текст сообщения
                await callback.message.edit_text(
                    text=text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])  # Пустая разметка для удаления кнопок
                )
                logger.debug(f"Edited text for message {callback.message.message_id}")
        except TelegramBadRequest as e:
            logger.error(f"Ошибка редактирования сообщения для акции {promotion_id}: {e}")
            # Если редактирование не удалось, отправляем новое сообщение
            await callback.message.answer(
                text=text,
                parse_mode="HTML"
            )
        
        # Подтверждаем обработку callback
        await callback.answer()

    except ValueError:
        logger.error(f"Некорректный ID акции в callback_data: {callback.data}")
        try:
            if callback.message.content_type == 'photo':
                await callback.message.edit_caption(
                    caption="Ошибка: Некорректный ID акции.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
            else:
                await callback.message.edit_text(
                    text="Ошибка: Некорректный ID акции.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
        except TelegramBadRequest as e:
            logger.error(f"Ошибка редактирования сообщения при ValueError: {e}")
            await callback.message.answer(
                text="Ошибка: Некорректный ID акции.",
                parse_mode="HTML"
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при подтверждении акции {promotion_id}: {e}")
        try:
            if callback.message.content_type == 'photo':
                await callback.message.edit_caption(
                    caption="Произошла ошибка при подтверждении акции.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
            else:
                await callback.message.edit_text(
                    text="Произошла ошибка при подтверждении акции.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
        except TelegramBadRequest as e:
            logger.error(f"Ошибка редактирования сообщения при Exception: {e}")
            await callback.message.answer(
                text="Произошла ошибка при подтверждении акции.",
                parse_mode="HTML"
            )
        await callback.answer()

@admin_promotion_router.callback_query(F.data.startswith("reject_promotion:"))
async def handle_reject_promotion(callback: CallbackQuery):
    """
    Обрабатывает нажатие кнопки "Отклонить" для акции.
    """
    logger.debug(f"Получен CallbackQuery: data={callback.data}, user_id={callback.from_user.id}, message_type={callback.message.content_type}")
    
    try:
        # Извлекаем ID акции из callback_data
        promotion_id = int(callback.data.split(":")[1])
        
        # Обновляем статус акции через API
        success = await update_promotion_approval(promotion_id, approve=False)
        
        # Формируем текст ответа
        text = f"Акция с ID {promotion_id} отклонена и удалена." if success else f"Ошибка при отклонении акции с ID {promotion_id}."
        
        # Проверяем тип сообщения
        try:
            if callback.message.content_type == 'photo':
                # Редактируем подпись фото
                await callback.message.edit_caption(
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])  # Пустая разметка для удаления кнопок
                )
                logger.debug(f"Edited caption for photo message {callback.message.message_id}")
            else:
                # Редактируем текст сообщения
                await callback.message.edit_text(
                    text=text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])  # Пустая разметка для удаления кнопок
                )
                logger.debug(f"Edited text for message {callback.message.message_id}")
        except TelegramBadRequest as e:
            logger.error(f"Ошибка редактирования сообщения для акции {promotion_id}: {e}")
            # Если редактирование не удалось, отправляем новое сообщение
            await callback.message.answer(
                text=text,
                parse_mode="HTML"
            )
        
        # Подтверждаем обработку callback
        await callback.answer()

    except ValueError:
        logger.error(f"Некорректный ID акции в callback_data: {callback.data}")
        try:
            if callback.message.content_type == 'photo':
                await callback.message.edit_caption(
                    caption="Ошибка: Некорректный ID акции.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
            else:
                await callback.message.edit_text(
                    text="Ошибка: Некорректный ID акции.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
        except TelegramBadRequest as e:
            logger.error(f"Ошибка редактирования сообщения при ValueError: {e}")
            await callback.message.answer(
                text="Ошибка: Некорректный ID акции.",
                parse_mode="HTML"
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при отклонении акции {promotion_id}: {e}")
        try:
            if callback.message.content_type == 'photo':
                await callback.message.edit_caption(
                    caption="Произошла ошибка при отклонении акции.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
            else:
                await callback.message.edit_text(
                    text="Произошла ошибка при отклонении акции.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
        except TelegramBadRequest as e:
            logger.error(f"Ошибка редактирования сообщения при Exception: {e}")
            await callback.message.answer(
                text="Произошла ошибка при отклонении акции.",
                parse_mode="HTML"
            )
        await callback.answer()
