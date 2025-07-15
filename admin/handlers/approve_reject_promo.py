from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
import aiohttp
import logging
from data.config import config_settings
from data.url import url_promotions
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID
from datetime import datetime

logger = logging.getLogger(__name__)

# Роутер для админских действий
admin_promotion_router = Router()
admin_promotion_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([ADMIN_CHAT_ID], show_message=False)
)

# Обновляет статус подтверждения акции через API
async def update_promotion_approval(promotion_id: int, approve: bool) -> bool:
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

# Получает данные акции по ID через API
async def get_promotion_details(promotion_id: int) -> dict:
    url = f"{url_promotions}{promotion_id}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    logger.info(f"Данные акции {promotion_id} успешно получены")
                    return await resp.json()
                else:
                    logger.error(f"Ошибка при получении данных акции {promotion_id}: status={resp.status}")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"Ошибка при получении данных акции {promotion_id}: {e}")
        return None
    
# Форматирует текст с полной информацией об акции
def format_promotion_text(promotion: dict) -> str:
    start_date = datetime.fromisoformat(promotion['start_date'].replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
    end_date = datetime.fromisoformat(promotion['end_date'].replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
    return (
        f"<b>Акция подтверждена: {promotion['title']}</b>\n\n"
        f"Период: {start_date} - {end_date}\n\n"
        f"{promotion['discount_or_bonus'].capitalize()}: {promotion['discount_or_bonus_value']}{'%' if promotion['discount_or_bonus'] == 'скидка' else ''}\n\n"
        f"{promotion['description']}\n\n"
        f"Ссылка: {promotion['url']}\n"
        f"Статус: Подтверждена"
    )

# Обрабатывает нажатие кнопки "Подтвердить" для акции
@admin_promotion_router.callback_query(F.data.startswith("approve_promotion:"))
async def handle_approve_promotion(callback: CallbackQuery):
    logger.debug(f"Получен CallbackQuery: data={callback.data}, user_id={callback.from_user.id}, message_type={callback.message.content_type}")
    
    try:
        promotion_id = int(callback.data.split(":")[1])
        
        success = await update_promotion_approval(promotion_id, approve=True)
        
        if success:
            promotion = await get_promotion_details(promotion_id)
            if not promotion:
                logger.error(f"Не удалось получить данные акции {promotion_id} после подтверждения")
                text = f"Ошибка: Не удалось получить данные акции с ID {promotion_id}."
            else:
                text = format_promotion_text(promotion)
        else:
            text = f"Ошибка при подтверждении акции с ID {promotion_id}."
        
        try:
            if callback.message.content_type == 'photo' and success and promotion:
                await callback.message.edit_caption(
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
                )
                logger.debug(f"Edited caption for photo message {callback.message.message_id}")
            else:
                await callback.message.edit_text(
                    text=text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[]) 
                )
                logger.debug(f"Edited text for message {callback.message.message_id}")
        except TelegramBadRequest as e:
            logger.error(f"Ошибка редактирования сообщения для акции {promotion_id}: {e}")
            if success and promotion and callback.message.content_type == 'photo':
                await callback.message.answer_photo(
                    photo=promotion.get("photo"),
                    caption=text,
                    parse_mode="HTML"
                )
            else:
                await callback.message.answer(
                    text=text,
                    parse_mode="HTML"
                )
        
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

# Обрабатывает нажатие кнопки "Отклонить" для акции
@admin_promotion_router.callback_query(F.data.startswith("reject_promotion:"))
async def handle_reject_promotion(callback: CallbackQuery):
    logger.debug(f"Получен CallbackQuery: data={callback.data}, user_id={callback.from_user.id}, message_type={callback.message.content_type}")
    
    try:
        promotion_id = int(callback.data.split(":")[1])
        
        success = await update_promotion_approval(promotion_id, approve=False)
        
        text = f"Акция с ID {promotion_id} отклонена и удалена." if success else f"Ошибка при отклонении акции с ID {promotion_id}."
        
        try:
            if callback.message.content_type == 'photo':
                await callback.message.edit_caption(
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[]) 
                )
                logger.debug(f"Edited caption for photo message {callback.message.message_id}")
            else:
                # Редактируем текст сообщения
                await callback.message.edit_text(
                    text=text,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[])  
                )
                logger.debug(f"Edited text for message {callback.message.message_id}")
        except TelegramBadRequest as e:
            logger.error(f"Ошибка редактирования сообщения для акции {promotion_id}: {e}")
            await callback.message.answer(
                text=text,
                parse_mode="HTML"
            )

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