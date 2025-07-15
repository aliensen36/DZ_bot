import re
import aiohttp
import logging
from datetime import datetime, timezone, timedelta
from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ContentType

from data.config import config_settings
from data.url import url_promotions
from resident_admin.keyboards.res_admin_reply import res_admin_promotion_keyboard, res_admin_keyboard, res_admin_cancel_keyboard, res_admin_edit_promotion_keyboard
from utils.filters import ChatTypeFilter, IsGroupAdmin, RESIDENT_ADMIN_CHAT_ID
from utils.dowload_photo import download_photo_from_telegram
from utils.calendar import get_calendar, get_time_keyboard

logger = logging.getLogger(__name__)

RA_promotion_router = Router()
RA_promotion_router.message.filter(ChatTypeFilter("private"))

URL_PATTERN = re.compile(
    r'^(https?://)?'
    r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
    r'(:\d+)?'
    r'(/[\w\-._~:/?#[\]@!$&\'()*+,;=]*)?$'
)

DISCOUNT_PATTERN = re.compile(r'^\s*скидка\s*(\d+\.?\d*)\s*%?\s*$', re.IGNORECASE)
BONUS_PATTERN = re.compile(r'^\s*бонус(?:ов)?\s*(\d+\.?\d*)\s*$', re.IGNORECASE)

MOSCOW_TZ = timezone(timedelta(hours=3))

class PromotionForm(StatesGroup):
    waiting_for_title = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_start_date = State()
    waiting_for_start_time = State()
    waiting_for_end_date = State()
    waiting_for_end_time = State()
    waiting_for_discount_or_bonus = State()
    waiting_for_url = State()

class PromotionEditForm(StatesGroup):
    choosing_field = State()
    waiting_for_title = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_start_date = State()
    waiting_for_start_time = State()
    waiting_for_end_date = State()
    waiting_for_end_time = State()
    waiting_for_discount_or_bonus = State()
    waiting_for_url = State()

# =================================================================================================
# Вспомогательные функции
# =================================================================================================

# Создает инлайн-клавиатуру с кнопкой отмены
def inline_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])

# Форматирует дату и время в строковый формат
def format_datetime(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt_str or "-"

# =================================================================================================
# Функции для работы с БД
# =================================================================================================

# Создает новую акцию в базе данных
async def create_new_promotion(promotion_data: dict, photo_file_id: str = None, resident_id: int = None, bot=None):
    logger.info(f"Creating promotion for resident_id={resident_id}")
    url = f"{url_promotions}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    data = promotion_data.copy()

    if resident_id is None:
        logger.error("Resident ID is required but not provided")
        raise ValueError("Resident ID is required")

    form_data = aiohttp.FormData()
    for key, value in data.items():
        form_data.add_field(key, str(value))
    form_data.add_field("resident", str(resident_id))

    if photo_file_id and bot:
        try:
            photo_content = await download_photo_from_telegram(bot, photo_file_id)
            form_data.add_field(
                "photo",
                photo_content,
                filename=f"promotion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                content_type="image/jpeg"
            )
        except Exception as e:
            logger.error(f"Failed to download photo: {e}")
            raise Exception(f"Не удалось загрузить фото: {str(e)}")
    else:
        logger.error("Photo file_id or bot not provided")
        raise Exception("Фото обязательно для создания акции")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=form_data) as response:
                if response.status == 201:
                    logger.info(f"Promotion created successfully, status={response.status}")
                    return await response.json()
                else:
                    logger.error(f"Failed to create promotion, status={response.status}")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"HTTP Client Error creating promotion: {e}")
        return None

# Получает список акций для указанного резидента
async def get_promotion_list(resident_id: int):
    logger.info(f"Fetching promotion list for resident_id={resident_id}")
    url = f"{url_promotions}?resident={resident_id}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    logger.info(f"Successfully fetched promotions, status={resp.status}")
                    return await resp.json()
                else:
                    logger.error(f"Failed to fetch promotions, status={resp.status}")
                    return []
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching promotions: {e}")
        return []

# Получает акцию по названию
async def get_promotion_by_title(title: str, state: FSMContext) -> dict:
    data = await state.get_data()
    resident_id = data.get("resident_id")
    logger.info(f"Fetching promotion by title '{title}' for resident_id={resident_id}")
    promotions = await get_promotion_list(resident_id)
    for promotion in promotions:
        if promotion.get("title") == title:
            logger.info(f"Promotion found: {title}")
            return promotion
    logger.warning(f"Promotion with title '{title}' not found")
    return None

# Обновляет данные акции
async def update_promotion(promotion_id: int, updated_fields: dict, bot: Bot = None):
    logger.info(f"Updating promotion {promotion_id} with fields: {updated_fields.keys()}")
    url = f"{url_promotions}{promotion_id}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    form_data = aiohttp.FormData()

    for key, value in updated_fields.items():
        if key == "photo" and value and bot:
            try:
                photo_content = await download_photo_from_telegram(bot, value)
                form_data.add_field(
                    "photo",
                    photo_content,
                    filename=f"promotion_{promotion_id}.jpg",
                    content_type="image/jpeg"
                )
            except Exception as e:
                logger.error(f"Failed to download photo for update: {e}")
                raise
        else:
            form_data.add_field(key, str(value))

    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, data=form_data) as response:
                if response.status == 200:
                    logger.info(f"Promotion {promotion_id} updated successfully, status={response.status}")
                    return await response.json()
                else:
                    logger.error(f"Failed to update promotion {promotion_id}, status={response.status}")
                    return False
    except Exception as e:
        logger.error(f"Error updating promotion {promotion_id}: {e}")
        return False

# Удаляет акцию из базы данных
async def delete_promotion(promotion_id: int) -> bool:
    logger.info(f"Deleting promotion {promotion_id}")
    url = f"{url_promotions}{promotion_id}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as resp:
                if resp.status in (200, 204):
                    logger.info(f"Promotion {promotion_id} deleted successfully, status={resp.status}")
                    return True
                else:
                    logger.error(f"Failed to delete promotion {promotion_id}, status={resp.status}")
                    return False
    except Exception as e:
        logger.error(f"Error deleting promotion {promotion_id}: {e}")
        return False

# =================================================================================================
# Обработчики сообщений и callback-запросов
# =================================================================================================

# Обрабатывает команду сброса формы
@RA_promotion_router.message(F.text == "Сбросить", StateFilter(PromotionForm, PromotionEditForm))
async def cancel_promotion_creation(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} cancelled promotion creation/editing")
    await state.clear()
    await message.answer("Вы вернулись в меню акций.", reply_markup=res_admin_promotion_keyboard())

# Возвращает в главное меню администратора
@RA_promotion_router.message(F.text == "↩ Обратно")
async def back_to_res_admin_menu(message: Message):
    logger.info(f"User {message.from_user.id} returned to admin menu")
    await message.answer(
        "Вы вернулись в главное меню администратора.",
        reply_markup=res_admin_keyboard()
    )

# Отображает меню управления акциями
@RA_promotion_router.message(F.text == "Акции")
async def handle_promotions(message: Message):
    logger.info(f"User {message.from_user.id} accessed promotions menu")
    await message.answer(
        "Управление акциями:",
        reply_markup=res_admin_promotion_keyboard()
    )

# Начинает процесс создания новой акции
@RA_promotion_router.message(F.text == "Создать акцию")
async def handle_add_promotion(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} started creating a new promotion")
    await state.set_state(PromotionForm.waiting_for_title)
    await message.answer(
        "Введите название акции:",
        reply_markup=res_admin_cancel_keyboard()
    )

# Обрабатывает ввод названия акции
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_title))
async def process_promotion_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        logger.warning(f"User {message.from_user.id} provided empty title")
        await message.answer("Название не может быть пустым. Пожалуйста, введите название акции:", reply_markup=res_admin_cancel_keyboard())
        return
    await state.update_data(title=title)
    await state.set_state(PromotionForm.waiting_for_photo)
    await message.answer("Отправьте фото для акции:", reply_markup=res_admin_cancel_keyboard())

# Обрабатывает загрузку фото акции с валидацией формата
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_photo))
async def process_promotion_photo(message: Message, state: FSMContext):
    if message.content_type != ContentType.PHOTO:
        logger.warning(f"User {message.from_user.id} uploaded non-photo content: {message.content_type}")
        await message.answer("Пожалуйста, отправьте изображение в формате JPG или PNG.", reply_markup=res_admin_cancel_keyboard())
        return
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        if message.photo[-1].file_size > 10 * 1024 * 1024:
            logger.warning(f"User {message.from_user.id} uploaded photo exceeding 10MB")
            await message.answer("Фото слишком большое. Максимальный размер: 10 МБ.", reply_markup=res_admin_cancel_keyboard())
            return
        await state.update_data(photo=photo_file_id)
        await state.set_state(PromotionForm.waiting_for_description)
        await message.answer("Фото получено. Введите описание акции:", reply_markup=res_admin_cancel_keyboard())
    else:
        logger.warning(f"User {message.from_user.id} failed to upload photo")
        await message.answer("Пожалуйста, отправьте изображение в формате JPG или PNG.", reply_markup=res_admin_cancel_keyboard())

# Обрабатывает ввод описания акции
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_description))
async def process_promotion_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if not description:
        logger.warning(f"User {message.from_user.id} provided empty description")
        await message.answer("Описание не может быть пустым. Пожалуйста, введите описание акции:", reply_markup=res_admin_cancel_keyboard())
        return
    await state.update_data(description=description)
    await state.set_state(PromotionForm.waiting_for_start_date)
    await message.answer("Выберите дату начала акции:", reply_markup=get_calendar())


@RA_promotion_router.callback_query(F.data == "ignore")
async def process_ignore_callback(callback: CallbackQuery):
    logger.debug(f"Ignore callback received from user {callback.from_user.id}")
    await callback.answer()

# Обрабатывает выбор даты начала акции
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_start_date))
async def process_start_date_selection(message: Message, state: FSMContext):
    await message.answer(
        "Выберите дату начала акции:",
        reply_markup=get_calendar(prefix="promo_")
    )

# Обрабатывает выбор даты окончания акции
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_end_date))
async def process_end_date_selection(message: Message, state: FSMContext):
    await message.answer(
        "Выберите дату окончания акции:",
        reply_markup=get_calendar(prefix="promo_")
    )

# Обрабатывает выбор даты через callback
@RA_promotion_router.callback_query(F.data.startswith("promo_select_date:"))
async def process_date_callback(callback: CallbackQuery, state: FSMContext):

    current_state = await state.get_state()
    logger.debug(f"Processing date callback, state={current_state}, callback_data={callback.data}, user_id={callback.from_user.id}")

    date_str = callback.data[len("promo_select_date:"):]  # Извлекаем дату без префикса
    try:
        selected_date = datetime.strptime(date_str, "%d.%m.%Y").replace(tzinfo=MOSCOW_TZ)
        current_time = datetime.now(MOSCOW_TZ)
        if selected_date.date() < current_time.date():
            logger.warning(f"User {callback.from_user.id} selected past date: {date_str}")
            await callback.message.edit_text(
                "Дата не может быть в прошлом. Пожалуйста, выберите другую дату:",
                reply_markup=get_calendar(prefix="promo_")
            )
            await callback.answer()
            return

        current_state = await state.get_state()
        if current_state == PromotionForm.waiting_for_start_date.state:
            await state.update_data(start_date=selected_date)
            await state.set_state(PromotionForm.waiting_for_start_time)
            await callback.message.edit_text(
                f"Выбрана дата начала: {date_str}. Выберите время начала:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
        elif current_state == PromotionForm.waiting_for_end_date.state:
            data = await state.get_data()
            start_date = data.get("start_date")
            if selected_date.date() < start_date.date():
                logger.warning(f"User {callback.from_user.id} selected end date {date_str} before start date")
                await callback.message.edit_text(
                    "Дата окончания не может быть раньше даты начала. Выберите другую дату:",
                    reply_markup=get_calendar(prefix="promo_")
                )
                await callback.answer()
                return
            await state.update_data(end_date=selected_date)
            await state.set_state(PromotionForm.waiting_for_end_time)
            await callback.message.edit_text(
                f"Выбрана дата окончания: {date_str}. Выберите время окончания:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
        elif current_state == PromotionEditForm.waiting_for_start_date.state:
            if selected_date.date() < current_time.date():
                logger.warning(f"User {callback.from_user.id} selected past start date: {date_str}")
                await callback.message.edit_text(
                    "Дата начала не может быть в прошлом. Выберите другую дату:",
                    reply_markup=get_calendar(prefix="promo_")
                )
                await callback.answer()
                return
            await state.update_data(start_date=selected_date)
            await state.set_state(PromotionEditForm.waiting_for_start_time)
            await callback.message.edit_text(
                f"Выбрана дата начала: {date_str}. Выберите время начала:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
        elif current_state == PromotionEditForm.waiting_for_end_date.state:
            data = await state.get_data()
            promotion = data.get("promotion")
            start_date = datetime.fromisoformat(promotion["start_date"].replace("Z", "+03:00")).date()
            if selected_date.date() < start_date:
                logger.warning(f"User {callback.from_user.id} selected end date {date_str} before start date")
                await callback.message.edit_text(
                    "Дата окончания не может быть раньше даты начала. Выберите другую дату:",
                    reply_markup=get_calendar(prefix="promo_")
                )
                await callback.answer()
                return
            await state.update_data(end_date=selected_date)
            await state.set_state(PromotionEditForm.waiting_for_end_time)
            await callback.message.edit_text(
                f"Выбрана дата окончания: {date_str}. Выберите время окончания:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
    except ValueError:
        logger.error(f"User {callback.from_user.id} provided invalid date format: {date_str}")
        await callback.message.edit_text(
            "Ошибка в формате даты. Попробуйте снова:",
            reply_markup=get_calendar(prefix="promo_")
        )
    await callback.answer()

# Обрабатывает навигацию по месяцам в календаре
@RA_promotion_router.callback_query(F.data.startswith(("promo_prev_month:", "promo_next_month:")))
async def process_month_navigation(callback: CallbackQuery, state: FSMContext):
    _, month, year = callback.data.split(":")
    month, year = int(month), int(year)
    await callback.message.edit_reply_markup(reply_markup=get_calendar(year, month, prefix="promo_"))
    await callback.answer()

# Обрабатывает запрос ручного ввода времени
@RA_promotion_router.callback_query(F.data == "promo_manual_time")
async def process_manual_time_request(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state in (PromotionForm.waiting_for_start_time.state, PromotionEditForm.waiting_for_start_time.state):
        await callback.message.edit_text(
            "Введите время начала (формат ЧЧ:ММ, например, 15:30):",
            reply_markup=inline_cancel_keyboard()
        )
    elif current_state in (PromotionForm.waiting_for_end_time.state, PromotionEditForm.waiting_for_end_time.state):
        await callback.message.edit_text(
            "Введите время окончания (формат ЧЧ:ММ, например, 15:30):",
            reply_markup=inline_cancel_keyboard()
        )
    await callback.answer()

# Обрабатывает выбор времени через callback
@RA_promotion_router.callback_query(F.data.startswith("promo_select_time:"))
async def process_time_callback(callback: CallbackQuery, state: FSMContext):

    current_state = await state.get_state()
    logger.debug(f"Processing time callback, state={current_state}, callback_data={callback.data}, user_id={callback.from_user.id}")

    time_str = callback.data[len("promo_select_time:"):]  # Извлекаем время без префикса
    try:
        if len(time_str) == 1 or (len(time_str) == 2 and time_str.isdigit()):
            time_str = f"{time_str.zfill(2)}:00"
        datetime.strptime(time_str, "%H:%M")
        current_state = await state.get_state()
        data = await state.get_data()
        
        if current_state == PromotionForm.waiting_for_start_time.state:
            start_date = data.get("start_date")
            start_datetime = datetime.strptime(f"{start_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            if start_datetime < datetime.now(MOSCOW_TZ):
                logger.warning(f"User {callback.from_user.id} selected past start time: {time_str}")
                await callback.message.edit_text(
                    "Время начала не может быть в прошлом. Выберите другое время:",
                    reply_markup=get_time_keyboard(prefix="promo_")
                )
                await callback.answer()
                return
            await state.update_data(start_datetime=start_datetime)
            await state.set_state(PromotionForm.waiting_for_end_date)
            await callback.message.edit_text(
                f"Время начала ({time_str}) сохранено. Выберите дату окончания:",
                reply_markup=get_calendar(prefix="promo_")
            )
        elif current_state == PromotionForm.waiting_for_end_time.state:
            end_date = data.get("end_date")
            end_datetime = datetime.strptime(f"{end_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            start_datetime = data.get("start_datetime")
            if end_datetime <= start_datetime:
                logger.warning(f"User {callback.from_user.id} selected end time {time_str} not after start time")
                await callback.message.edit_text(
                    "Время окончания должно быть позже времени начала. Выберите другое время:",
                    reply_markup=get_time_keyboard(prefix="promo_")
                )
                await callback.answer()
                return
            await state.update_data(end_datetime=end_datetime)
            await state.set_state(PromotionForm.waiting_for_discount_or_bonus)
            await callback.message.edit_text(
                f"Время окончания ({time_str}) сохранено. Введите скидку или бонус в формате 'Скидка 10%' или 'Бонусов 500':"
            )
        elif current_state == PromotionEditForm.waiting_for_start_time.state:
            start_date = data.get("start_date")
            start_datetime = datetime.strptime(f"{start_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            if start_datetime < datetime.now(MOSCOW_TZ):
                logger.warning(f"User {callback.from_user.id} selected past start time: {time_str}")
                await callback.message.edit_text(
                    "Время начала не может быть в прошлом. Выберите другое время:",
                    reply_markup=get_time_keyboard(prefix="promo_")
                )
                await callback.answer()
                return
            promotion = data.get("promotion")
            updated_promotion = await update_promotion(
                promotion_id=promotion["id"],
                updated_fields={"start_date": start_datetime.isoformat()},
                bot=None
            )
            if updated_promotion:
                promotion["start_date"] = updated_promotion.get("start_date", start_datetime.isoformat())
                end_datetime = datetime.fromisoformat(promotion["end_date"].replace("Z", "+03:00"))
                if end_datetime <= start_datetime:
                    logger.warning(f"User {callback.from_user.id} set end date {end_datetime} not after new start date {start_datetime}")
                    await callback.message.edit_text(
                        "Дата окончания должна быть позже новой даты начала. Пожалуйста, обновите дату окончания:",
                        reply_markup=get_calendar(prefix="promo_")
                    )
                    await state.set_state(PromotionEditForm.waiting_for_end_date)
                    await state.update_data(start_datetime=start_datetime, end_date=end_datetime)
                    await callback.answer()
                    return
                await state.update_data(promotion=updated_promotion)
                await callback.message.delete()
                await callback.message.answer(
                    f"Дата и время начала обновлены: {start_datetime.strftime('%d.%m.%Y %H:%M')}.",
                    reply_markup=res_admin_edit_promotion_keyboard()
                )
                await state.set_state(PromotionEditForm.choosing_field)
            else:
                logger.error(f"Failed to update start time for promotion {promotion['id']}")
                await callback.message.edit_text(
                    "Ошибка при обновлении времени начала. Попробуйте снова:",
                    reply_markup=get_time_keyboard(prefix="promo_")
                )
        elif current_state == PromotionEditForm.waiting_for_end_time.state:
            end_date = data.get("end_date")
            end_datetime = datetime.strptime(f"{end_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            promotion = data.get("promotion")
            start_datetime = datetime.fromisoformat(promotion["start_date"].replace("Z", "+03:00"))
            if end_datetime <= start_datetime:
                logger.warning(f"User {callback.from_user.id} selected end time {time_str} not after start time")
                await callback.message.edit_text(
                    "Время окончания должно быть позже времени начала. Выберите другое время:",
                    reply_markup=get_time_keyboard(prefix="promo_")
                )
                await callback.answer()
                return
            updated_promotion = await update_promotion(
                promotion_id=promotion["id"],
                updated_fields={"end_date": end_datetime.isoformat()},
                bot=None
            )
            if updated_promotion:
                promotion["end_date"] = updated_promotion.get("end_date", end_datetime.isoformat())
                await state.update_data(promotion=updated_promotion)
                await callback.message.delete()
                await callback.message.answer(
                    f"Дата и время окончания обновлены: {end_datetime.strftime('%d.%m.%Y %H:%M')}.",
                    reply_markup=res_admin_edit_promotion_keyboard()
                )
                await state.set_state(PromotionEditForm.choosing_field)
            else:
                logger.error(f"Failed to update end time for promotion {promotion['id']}")
                await callback.message.edit_text(
                    "Ошибка при обновлении времени окончания. Попробуйте снова:",
                    reply_markup=get_time_keyboard(prefix="promo_")
                )
    except ValueError:
        logger.error(f"User {callback.from_user.id} provided invalid time format: {time_str}")
        await callback.message.edit_text(
            f"Неверный формат времени: '{time_str}'. Пожалуйста, выберите время в формате ЧЧ:ММ (например, 22:00):",
            reply_markup=get_time_keyboard(prefix="promo_")
        )
    await callback.answer()

# Обрабатывает ввод скидки или бонуса
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_discount_or_bonus))
async def process_discount_or_bonus(message: Message, state: FSMContext, bot):
    input_text = message.text.strip().lower()
    
    discount_match = DISCOUNT_PATTERN.match(input_text)
    bonus_match = BONUS_PATTERN.match(input_text)

    if discount_match:
        discount_value = float(discount_match.group(1))
        if discount_value <= 0 or discount_value > 100:
            logger.warning(f"User {message.from_user.id} provided invalid discount value: {discount_value}")
            await message.answer(
                "Значение скидки должно быть от 0 до 100%. Введите корректное значение, например 'Скидка 10%':",
                reply_markup=res_admin_cancel_keyboard()
            )
            return
        await state.update_data(discount_or_bonus="скидка", discount_or_bonus_value=discount_value)
    elif bonus_match:
        bonus_value = float(bonus_match.group(1))
        if bonus_value <= 0:
            logger.warning(f"User {message.from_user.id} provided invalid bonus value: {bonus_value}")
            await message.answer(
                "Значение бонуса должно быть больше 0. Введите корректное значение, например 'Бонусов 500':",
                reply_markup=res_admin_cancel_keyboard()
            )
            return
        await state.update_data(discount_or_bonus="бонус", discount_or_bonus_value=bonus_value)
    else:
        logger.warning(f"User {message.from_user.id} provided invalid discount/bonus format: {input_text}")
        await message.answer(
            "Неверный формат. Введите 'Скидка 10%' или 'Бонусов 500':",
            reply_markup=res_admin_cancel_keyboard()
        )
        return
    
    await state.set_state(PromotionForm.waiting_for_url)
    await message.answer(
        "Введите ссылку на участие в акции:",
        reply_markup=res_admin_cancel_keyboard()
    )

# Обрабатывает ввод URL и создает акцию
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_url))
async def process_promotion_url_and_create(message: Message, state: FSMContext, bot):
    url = message.text.strip()
    if not url:
        logger.warning(f"User {message.from_user.id} provided empty URL")
        await message.answer(
            "Ссылка для участия в акции не может быть пустой. Пожалуйста, введите ссылку:",
            reply_markup=res_admin_cancel_keyboard()
        )
        return
    if not URL_PATTERN.match(url):
        logger.warning(f"User {message.from_user.id} provided invalid URL format: {url}")
        await message.answer(
            "Неверный формат ссылки. Пожалуйста, введите корректную ссылку для участия:",
            reply_markup=res_admin_cancel_keyboard()
        )
        return
    await state.update_data(url=url)

    data = await state.get_data()
    resident_id = data.get("resident_id")
    if not resident_id:
        logger.error(f"Resident ID not found for user_id={message.from_user.id}")
        await message.answer(
            "Ошибка: не удалось определить ID резидента. Пожалуйста, войдите в админ-панель заново с помощью команды /res_admin.",
            reply_markup=res_admin_promotion_keyboard()
        )
        await state.clear()
        return

    promotion_data = {
        "title": data.get("title"),
        "description": data.get("description"),
        "start_date": data.get("start_datetime").isoformat(),
        "end_date": data.get("end_datetime").isoformat(),
        "url": data.get("url"),
        "discount_or_bonus": data.get("discount_or_bonus"),
        "discount_or_bonus_value": data.get("discount_or_bonus_value"),
    }
    photo_file_id = data.get("photo")

    created_promotion = await create_new_promotion(promotion_data, photo_file_id, resident_id, bot)
    if created_promotion:
        logger.info(f"Promotion created successfully for user_id={message.from_user.id}, title={promotion_data['title']}")
        caption=(
            f"Акция успешно создана!\n"
            f"Название: {promotion_data['title']}\n"
            f"Описание: {promotion_data['description']}\n"
            f"Дата начала: {format_datetime(promotion_data.get('start_date'))}\n"
            f"Дата окончания: {format_datetime(promotion_data.get('end_date'))}\n"
            f"Ссылка для участия: {promotion_data['url']}\n"
            f"{promotion_data['discount_or_bonus'].capitalize()}: {promotion_data['discount_or_bonus_value']}{'%' if promotion_data['discount_or_bonus'] == 'скидка' else ''}\n"
            f"Ожидайте подтверждения от администратора."
        )

        photo_url=created_promotion.get("photo")
        if photo_url:
            await message.answer_photo(
                photo=photo_url,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=res_admin_promotion_keyboard(),
            )

        await state.clear()
    else:
        logger.error(f"Failed to create promotion for user_id={message.from_user.id}")
        await message.answer(
            "Произошла ошибка при создании акции. Пожалуйста, проверьте данные и попробуйте еще раз.",
            reply_markup=res_admin_promotion_keyboard()
        )
        await state.clear()

# Начинает процесс редактирования акции
@RA_promotion_router.message(F.text == "Изменить акцию")
async def edit_promotion_start(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} started editing a promotion")
    data = await state.get_data()
    resident_id = data.get("resident_id")
    promotions = await get_promotion_list(resident_id)
    if not promotions:
        logger.info(f"No promotions available for user_id={message.from_user.id}")
        await message.answer("Нет доступных акций для редактирования")
        return

    builder = ReplyKeyboardBuilder()
    for promotion in promotions:
        title = promotion.get("title")
        builder.button(text=f"🖋️ {title}")
    builder.button(text="↩ Обратно")
    builder.adjust(1)

    await message.answer(
        "Выберите акцию для редактирования:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Выбирает акцию для редактирования
@RA_promotion_router.message(F.text.startswith("🖋️ "))
async def edit_promotion_select(message: Message, state: FSMContext):
    promotion_title = message.text[2:].strip()
    promotion = await get_promotion_by_title(promotion_title, state)

    if not promotion:
        logger.warning(f"Promotion {promotion_title} not found for user_id={message.from_user.id}")
        await message.answer("Не удалось найти акцию.")
        return

    await state.clear()
    await state.set_state(PromotionEditForm.choosing_field)
    await state.update_data(promotion=promotion)

    current_promotion_text = (
        f"Название: {promotion['title']}\n"
        f"Описание: {promotion['description']}\n"
        f"Дата начала: {format_datetime(promotion.get('start_date'))}\n"
        f"Дата окончания: {format_datetime(promotion.get('end_date'))}\n"
        f"Ссылка для участия: {promotion['url']}\n"
    )

    photo_url = promotion.get("photo")
    if photo_url:
        try:
            await message.answer_photo(
                photo=photo_url,
                caption=current_promotion_text,
                parse_mode="Markdown",
                reply_markup=res_admin_edit_promotion_keyboard()
            )
        except Exception as e:
            logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
            await message.answer(
                current_promotion_text + "\n\n(Фото недоступно)",
                reply_markup=res_admin_edit_promotion_keyboard()
            )
    else:
        await message.answer(
            current_promotion_text + "\n\n(Фото отсутствует)",
            reply_markup=res_admin_edit_promotion_keyboard()
        )

# Начинает редактирование названия акции
@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить название")
async def edit_promotion_title(message: Message, state: FSMContext):
    await message.answer("Введите новое название:", reply_markup=res_admin_cancel_keyboard())
    await state.set_state(PromotionEditForm.waiting_for_title)

# Начинает редактирование фото акции
@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить фото")
async def edit_promotion_photo(message: Message, state: FSMContext):
    await message.answer("Отправьте новое фото:", reply_markup=res_admin_cancel_keyboard())
    await state.set_state(PromotionEditForm.waiting_for_photo)

# Начинает редактирование описания акции
@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить описание")
async def edit_promotion_description(message: Message, state: FSMContext):
    await message.answer("Введите новое описание:", reply_markup=res_admin_cancel_keyboard())
    await state.set_state(PromotionEditForm.waiting_for_description)

# Начинает редактирование даты начала акции
@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить дату начала")
async def edit_promotion_start_date(message: Message, state: FSMContext):
    await message.answer("Выберите новую дату начала:", reply_markup=get_calendar())
    await state.set_state(PromotionEditForm.waiting_for_start_date)

# Начинает редактирование даты окончания акции
@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить дату окончания")
async def edit_promotion_end_date(message: Message, state: FSMContext):
    await message.answer("Выберите новую дату окончания:", reply_markup=get_calendar())
    await state.set_state(PromotionEditForm.waiting_for_end_date)

# Начинает редактирование ссылки акции
@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить ссылку")
async def edit_promotion_url(message: Message, state: FSMContext):
    await message.answer("Введите новую ссылку:", reply_markup=res_admin_cancel_keyboard())
    await state.set_state(PromotionEditForm.waiting_for_url)

# Начинает редактирование скидки или бонуса
@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить скидку/бонус")
async def edit_promotion_discount_or_bonus(message: Message, state: FSMContext):
    await message.answer(
        "Введите новую скидку или бонус в формате 'Скидка 10%' или 'Бонусов 500':",
        reply_markup=res_admin_cancel_keyboard()
    )
    await state.set_state(PromotionEditForm.waiting_for_discount_or_bonus)

# Обрабатывает ввод нового названия акции
@RA_promotion_router.message(PromotionEditForm.waiting_for_title)
async def process_promotion_title(message: Message, state: FSMContext):
    new_title = message.text.strip()
    if not new_title:
        logger.warning(f"User {message.from_user.id} provided empty title for update")
        await message.answer("Название не может быть пустым.", reply_markup=res_admin_cancel_keyboard())
        return
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        return
    updated_promotion = await update_promotion(promotion_id=promotion["id"], updated_fields={"title": new_title}, bot=None)
    if updated_promotion:
        logger.info(f"Promotion {promotion['id']} title updated to '{new_title}'")
        promotion["title"] = new_title
        await state.update_data(promotion=promotion)
        await message.answer("Название акции обновлено.", reply_markup=res_admin_edit_promotion_keyboard())
        await state.set_state(PromotionEditForm.choosing_field)
    else:
        logger.error(f"Failed to update title for promotion {promotion['id']}")
        await message.answer("Ошибка при обновлении названия. Попробуйте снова.", reply_markup=res_admin_edit_promotion_keyboard())

# Обрабатывает загрузку нового фото акции с валидацией формата
@RA_promotion_router.message(PromotionEditForm.waiting_for_photo)
async def process_promotion_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        return

    if message.content_type != ContentType.PHOTO:
        logger.warning(f"User {message.from_user.id} uploaded non-photo content: {message.content_type}")
        await message.answer("Пожалуйста, отправьте изображение в формате JPG или PNG.", reply_markup=res_admin_cancel_keyboard())
        return
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        if message.photo[-1].file_size > 10 * 1024 * 1024:
            logger.warning(f"User {message.from_user.id} uploaded photo exceeding 10MB")
            await message.answer("Фото слишком большое. Максимум 10 МБ.", reply_markup=res_admin_cancel_keyboard())
            return
        updated_promotion = await update_promotion(promotion_id=promotion["id"], updated_fields={"photo": photo_file_id}, bot=bot)
        if updated_promotion and isinstance(updated_promotion, dict):
            logger.info(f"Photo updated for promotion {promotion['id']}")
            promotion["photo"] = updated_promotion.get("photo")
            await state.update_data(promotion=promotion)
            await message.answer("Фото акции обновлено.", reply_markup=res_admin_edit_promotion_keyboard())
            await state.set_state(PromotionEditForm.choosing_field)
        else:
            logger.error(f"Failed to update photo for promotion {promotion['id']}")
            await message.answer("Ошибка при обновлении фото. Попробуйте снова.", reply_markup=res_admin_cancel_keyboard())
    else:
        logger.warning(f"User {message.from_user.id} failed to upload photo")
        await message.answer("Пожалуйста, отправьте изображение в формате JPG или PNG.", reply_markup=res_admin_cancel_keyboard())

# Обрабатывает ввод нового описания акции
@RA_promotion_router.message(PromotionEditForm.waiting_for_description)
async def process_promotion_description(message: Message, state: FSMContext):
    new_description = message.text.strip()
    if not new_description:
        logger.warning(f"User {message.from_user.id} provided empty description")
        await message.answer("Описание не может быть пустым.", reply_markup=res_admin_cancel_keyboard())
        return

    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        return

    updated_promotion = await update_promotion(promotion_id=promotion["id"], updated_fields={"description": new_description})
    if updated_promotion:
        logger.info(f"Description updated for promotion {promotion['id']}")
        promotion["description"] = new_description
        await state.update_data(promotion=promotion)
        await message.answer("Описание акции обновлено.", reply_markup=res_admin_edit_promotion_keyboard())
        await state.set_state(PromotionEditForm.choosing_field)
    else:
        logger.error(f"Failed to update description for promotion {promotion['id']}")
        await message.answer("Ошибка при обновлении описания. Попробуйте снова.", reply_markup=res_admin_edit_promotion_keyboard())

# Обрабатывает ввод новой ссылки акции
@RA_promotion_router.message(PromotionEditForm.waiting_for_url)
async def process_promotion_url(message: Message, state: FSMContext):
    new_url = message.text.strip()
    if not new_url:
        logger.warning(f"User {message.from_user.id} provided empty URL")
        await message.answer("Ссылка не может быть пустой.", reply_markup=res_admin_cancel_keyboard())
        return
    if not URL_PATTERN.match(new_url):
        logger.warning(f"User {message.from_user.id} provided invalid URL format: {new_url}")
        await message.answer("Неверный формат ссылки. Пожалуйста, введите корректную ссылку:", reply_markup=res_admin_cancel_keyboard())
        return
    
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        return

    updated_promotion = await update_promotion(promotion_id=promotion["id"], updated_fields={"url": new_url})
    if updated_promotion:
        logger.info(f"URL updated for promotion {promotion['id']}")
        promotion["url"] = new_url
        await state.update_data(promotion=promotion)
        await message.answer("Ссылка обновлена.", reply_markup=res_admin_edit_promotion_keyboard())
        await state.set_state(PromotionEditForm.choosing_field)
    else:
        logger.error(f"Failed to update URL for promotion {promotion['id']}")
        await message.answer("Ошибка при обновлении ссылки. Попробуйте снова.", reply_markup=res_admin_edit_promotion_keyboard())

# Обрабатывает ввод новой скидки или бонуса
@RA_promotion_router.message(PromotionEditForm.waiting_for_discount_or_bonus)
async def process_promotion_discount_or_bonus(message: Message, state: FSMContext):
    input_text = message.text.strip().lower()
    
    discount_match = DISCOUNT_PATTERN.match(input_text)
    bonus_match = BONUS_PATTERN.match(input_text)

    if discount_match:
        discount_value = float(discount_match.group(1))
        if discount_value <= 0 or discount_value > 100:
            logger.warning(f"User {message.from_user.id} provided invalid discount value: {discount_value}")
            await message.answer(
                "Значение скидки должно быть от 0 до 100%. Введите корректное значение, например 'Скидка 10%':",
                reply_markup=res_admin_cancel_keyboard()
            )
            return
        updated_fields = {"discount_or_bonus": "скидка", "discount_or_bonus_value": discount_value}
    elif bonus_match:
        bonus_value = float(bonus_match.group(1))
        if bonus_value <= 0:
            logger.warning(f"User {message.from_user.id} provided invalid bonus value: {bonus_value}")
            await message.answer(
                "Значение бонуса должно быть больше 0. Введите корректное значение, например 'Бонусов 500':",
                reply_markup=res_admin_cancel_keyboard()
            )
            return
        updated_fields = {"discount_or_bonus": "бонус", "discount_or_bonus_value": bonus_value}
    else:
        logger.warning(f"User {message.from_user.id} provided invalid discount/bonus format: {input_text}")
        await message.answer(
            "Неверный формат. Введите 'Скидка 10%' или 'Бонусов 500':",
            reply_markup=res_admin_cancel_keyboard()
        )
        return

    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_cancel_keyboard())
        await state.set_state(PromotionEditForm.choosing_field)
        return

    success = await update_promotion(promotion_id=promotion["id"], updated_fields=updated_fields)
    if success:
        logger.info(f"Discount/bonus updated for promotion {promotion['id']}")
        promotion["discount_or_bonus"] = updated_fields["discount_or_bonus"]
        promotion["discount_or_bonus_value"] = updated_fields["discount_or_bonus_value"]
        await state.update_data(promotion=promotion)
        await message.answer(
            f"{updated_fields['discount_or_bonus'].capitalize()} обновлен: {updated_fields['discount_or_bonus_value']}{'%' if updated_fields['discount_or_bonus'] == 'скидка' else ''}",
            reply_markup=res_admin_edit_promotion_keyboard()
        )
    else:
        logger.error(f"Failed to update discount/bonus for promotion {promotion['id']}")
        await message.answer(
            "Ошибка при обновлении скидки/бонуса. Попробуйте еще раз.",
            reply_markup=res_admin_edit_promotion_keyboard()
        )

    await state.set_state(PromotionEditForm.choosing_field)

# Начинает процесс удаления акции
@RA_promotion_router.message(F.text == "Удалить акцию")
async def delete_promotion_start(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} started deleting a promotion")
    data = await state.get_data()
    resident_id = data.get("resident_id")
    promotions = await get_promotion_list(resident_id)
    if not promotions:
        logger.info(f"No promotions available for deletion for user_id={message.from_user.id}")
        await message.answer("Нет доступных акций для удаления")
        return

    builder = ReplyKeyboardBuilder()
    for promotion in promotions:
        title = promotion.get("title")
        builder.button(text=f"❌ {title}")
    builder.button(text="Назад")
    builder.adjust(1)

    await message.answer(
        "Выберите акцию для удаления:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Выбирает акцию для удаления
@RA_promotion_router.message(F.text.startswith("❌ "))
async def delete_promotion_select(message: Message, state: FSMContext):
    promotion_title = message.text[2:].strip()
    promotion = await get_promotion_by_title(promotion_title, state)
    if not promotion:
        logger.warning(f"Promotion {promotion_title} not found for user_id={message.from_user.id}")
        await message.answer("Не удалось найти акцию.")
        return

    await state.update_data(promotion=promotion)
    current_promotion_text = (
        f"Название: {promotion['title']}\n"
        f"Описание: {promotion['description']}\n"
        f"Дата начала: {format_datetime(promotion.get('start_date'))}\n"
        f"Дата окончания: {format_datetime(promotion.get('end_date'))}\n"
        f"Ссылка для участия: {promotion['url']}\n"
    )

    builder = ReplyKeyboardBuilder()
    builder.button(text="Удалить")
    builder.button(text="Отмена")
    builder.adjust(1)

    photo_url = promotion.get("photo")
    if photo_url:
        try:
            await message.answer_photo(
                photo=photo_url,
                caption=f"Вы выбрали акцию:\n\n{current_promotion_text}\n\nВы действительно хотите удалить эту акцию?",
                parse_mode="Markdown",
                reply_markup=builder.as_markup(resize_keyboard=True)
            )
        except Exception as e:
            logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
            await message.answer(
                f"Вы выбрали акцию:\n\n{current_promotion_text}\n\n(Фото недоступно)\n\nВы действительно хотите удалить эту акцию?",
                reply_markup=builder.as_markup(resize_keyboard=True)
            )
    else:
        await message.answer(
            f"Вы выбрали акцию:\n\n{current_promotion_text}\n\n(Фото отсутствует)\n\nВы действительно хотите удалить эту акцию?",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )

# Подтверждает удаление акции
@RA_promotion_router.message(F.text == "Удалить")
async def confirm_delete_promotion(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка: акция не найдена.")
        return

    success = await delete_promotion(promotion_id=promotion["id"])
    if success:
        logger.info(f"Promotion {promotion['id']} deleted by user_id={message.from_user.id}")
        await message.answer("Акция успешно удалена.", reply_markup=res_admin_promotion_keyboard())
    else:
        logger.error(f"Failed to delete promotion {promotion['id']} for user_id={message.from_user.id}")
        await message.answer("Не удалось удалить акцию. Попробуйте снова.", reply_markup=res_admin_promotion_keyboard())
    await state.clear()