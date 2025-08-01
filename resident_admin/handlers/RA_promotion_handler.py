import re
import aiohttp
import logging
from datetime import datetime
from decimal import Decimal

from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from data.config import config_settings
from data.url import url_promotions
from resident_admin.keyboards.res_admin_reply import res_admin_promotion_keyboard, res_admin_keyboard, res_admin_cancel_keyboard, res_admin_edit_promotion_keyboard
from utils.filters import ChatTypeFilter
from utils.photo import download_photo_from_telegram, validate_photo
from utils.calendar import get_calendar, get_time_keyboard, format_datetime
from utils.constants import MOSCOW_TZ, TIME_PATTERN
from resident_admin.services.resident_required import resident_required

# Настройка логирования
logger = logging.getLogger(__name__)

# Роутеры
RA_promotion_router = Router()
RA_promotion_router.message.filter(ChatTypeFilter("private"))

# =================================================================================================
# Состояния FSM
# =================================================================================================

class PromotionForm(StatesGroup):
    waiting_for_title = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_start_date = State()
    waiting_for_start_time = State()
    waiting_for_end_date = State()
    waiting_for_end_time = State()
    waiting_for_discount_percent = State()
    waiting_for_promo_code = State()

class PromotionEditForm(StatesGroup):
    choosing_field = State()
    waiting_for_title = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_start_date = State()
    waiting_for_start_time = State()
    waiting_for_end_date = State()
    waiting_for_end_time = State()
    waiting_for_discount_percent = State()
    waiting_for_promo_code = State()

class DeletePromotionForm(StatesGroup):
    waiting_for_confirmation = State()

# =================================================================================================
# Вспомогательные функции
# =================================================================================================

def format_promotion_text(promotion: dict) -> str:
    return (
        f"<b>Акция обновлена: {promotion['title']}</b>\n\n"
        f"Описание: {promotion['description']}\n\n"
        f"Период: {format_datetime(promotion.get('start_date'))} - {format_datetime(promotion.get('end_date'))}\n\n"
        f"Скидка: {promotion['discount_percent']}{'%'}\n\n"
        f"Промокод: {promotion['promotional_code']}\n"
        f"Статус: {'Подтверждена' if promotion.get('is_approved', False) else 'Ожидае подтверждения'}"
    )

async def handle_missing_promotion(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    if data.get("resident_id"):
        await state.update_data(resident_id=data["resident_id"], resident_name=data["resident_name"])
    await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())

async def finish_edit_promotion(message, state, updated_promotion, promotion, data):
    if updated_promotion:
        await state.update_data(promotion=updated_promotion)
        text = format_promotion_text(updated_promotion)
        photo_url = updated_promotion.get("photo")
        if photo_url:
            try:
                await message.answer_photo(
                    photo=photo_url,
                    caption=f"{text}\n\nРедактирование завершено. Ожидайте подтверждения администратора.",
                    parse_mode="HTML",
                    reply_markup=res_admin_promotion_keyboard()
                )
            except Exception:
                await message.answer(
                    f"{text}\n\n(Фото недоступно)\n\nРедактирование завершено.",
                    parse_mode="HTML",
                    reply_markup=res_admin_promotion_keyboard()
                )
        else:
            await message.answer(
                f"{text}\n\n(Фото отсутствует)\n\nРедактирование завершено.",
                parse_mode="HTML",
                reply_markup=res_admin_promotion_keyboard()
            )
        await state.set_state(PromotionEditForm.waiting_for_title)
    else:
        await handle_missing_promotion(message, state)

# =================================================================================================
# Функции для работы с БД
# =================================================================================================

async def create_new_promotion(promotion_data: dict, photo_file_id: str = None, resident_id: int = None, bot=None):
    logger.info(f"Creating promotion for resident_id={resident_id}")
    url = f"{url_promotions}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    data = promotion_data.copy()
    form_data = aiohttp.FormData()
    for key, value in data.items():
        logger.info(f"Adding field to FormData: {key}={value}")
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

async def update_promotion(promotion_id: int, updated_fields: dict, bot: Bot = None):
    logger.info(f"Updating promotion {promotion_id} with fields: {updated_fields}")  # Логируем полное содержимое
    url = f"{url_promotions}{promotion_id}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    form_data = aiohttp.FormData()
    for key, value in updated_fields.items():
        logger.info(f"{key}={value}")
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
            if value is None:
                logger.warning(f"Skipping None value for key {key} in promotion {promotion_id}")
                continue  # Пропускаем None
            form_data.add_field(key, str(value))
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, data=form_data) as response:
                response_text = await response.text()  # Захватываем тело ответа
                if response.status == 200:
                    logger.info(f"Promotion {promotion_id} updated successfully, status={response.status}")
                    return await response.json()
                else:
                    logger.error(f"Failed to update promotion {promotion_id}, status={response.status}, response={response_text}")
                    return False
    except Exception as e:
        logger.error(f"Error updating promotion {promotion_id}: {e}")
        return False

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
# Обработчики Сбросить, Обратно, Акции
# =================================================================================================

@RA_promotion_router.message(F.text == "Сбросить", StateFilter(PromotionForm, PromotionEditForm, DeletePromotionForm))
@resident_required
async def cancel_promotion_action(message: Message, state: FSMContext):
    logger.debug(f"Cancel action requested by user {message.from_user.id} in state {await state.get_state()}")
    data = await state.get_data()
    resident_id = data.get("resident_id")
    resident_name = data.get("resident_name")
    await state.clear()
    if resident_id:
        await state.update_data(resident_id=resident_id, resident_name=resident_name)
    await message.answer(
        "Действие отменено.",
        reply_markup=res_admin_promotion_keyboard()
    )

@RA_promotion_router.message(F.text == "↩ Обратно")
@resident_required
async def back_to_res_admin_menu(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} returned to admin menu")
    data = await state.get_data()
    resident_id = data.get("resident_id")
    resident_name = data.get("resident_name")
    await state.clear()
    if resident_id:
        await state.update_data(resident_id=resident_id, resident_name=resident_name)
    await message.answer(
        "Вы вернулись в главное меню администратора.",
        reply_markup=res_admin_keyboard()
    )

@RA_promotion_router.message(F.text == "Акции")
@resident_required
async def handle_promotions(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} accessed promotions menu")
    await message.answer(
        "Управление акциями:",
        reply_markup=res_admin_promotion_keyboard()
    )

# =================================================================================================
# Обработчики создания акции
# =================================================================================================

@RA_promotion_router.message(F.text == "Создать акцию")
@resident_required
async def handle_add_promotion(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} started creating a new promotion")
    await state.set_state(PromotionForm.waiting_for_title)
    await message.answer(
        "Введите название акции:",
        reply_markup=res_admin_cancel_keyboard()
    )

@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_title))
@resident_required
async def process_promotion_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        logger.warning(f"User {message.from_user.id} provided empty title")
        await message.answer("Название не может быть пустым. Пожалуйста, введите название акции:", reply_markup=res_admin_cancel_keyboard())
        return
    await state.update_data(title=title)
    await state.set_state(PromotionForm.waiting_for_photo)
    await message.answer("Отправьте фото для акции:", reply_markup=res_admin_cancel_keyboard())

@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_photo))
@resident_required
async def process_promotion_photo(message: Message, state: FSMContext, bot: Bot):
    is_valid, result = await validate_photo(message)
    if not is_valid:
        await message.answer(result, reply_markup=res_admin_cancel_keyboard())
        return
    photo_file_id = result
    await state.update_data(photo=photo_file_id)
    await state.set_state(PromotionForm.waiting_for_description)
    await message.answer("Фото получено. Введите описание акции:", reply_markup=res_admin_cancel_keyboard())

@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_description))
@resident_required
async def process_promotion_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if not description:
        logger.warning(f"User {message.from_user.id} provided empty description")
        await message.answer("Описание не может быть пустым. Пожалуйста, введите описание акции:", reply_markup=res_admin_cancel_keyboard())
        return
    await state.update_data(description=description)
    await state.set_state(PromotionForm.waiting_for_start_date)
    await message.answer("Выберите дату начала акции:", reply_markup=get_calendar(prefix="promo_"))

@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_discount_percent))
@resident_required
async def process_discount_percent(message: Message, state: FSMContext, bot: Bot):
    discount_input = message.text.strip()
    try:
        discount_percent = Decimal(discount_input)
        if discount_percent < 0 or discount_percent > 100:
            logger.warning(f"User {message.from_user.id} provided invalid discount percent: {discount_input}")
            await message.answer(
                "Процент скидки должен быть в диапазоне от 0 до 100. Пожалуйста, введите корректный процент:",
                reply_markup=res_admin_cancel_keyboard(),
                parse_mode=None
            )
            return
        if discount_percent.as_tuple().exponent < -2: 
            logger.warning(f"User {message.from_user.id} provided too many decimal places: {discount_input}")
            await message.answer(
                "Процент скидки должен иметь не более двух знаков после запятой (например, 10 или 10.50):",
                reply_markup=res_admin_cancel_keyboard(),
                parse_mode=None
            )
            return
        discount_percent_str = f"{discount_percent:.2f}"
    except ValueError:
        logger.warning(f"User {message.from_user.id} provided non-numeric discount percent: {discount_input}")
        await message.answer(
            "Пожалуйста, введите число для процента скидки (например, 10 или 10.50):",
            reply_markup=res_admin_cancel_keyboard(),
            parse_mode=None
        )
        return
    await state.update_data(discount_percent=discount_percent_str)
    logger.info(f"Discount percent saved for user {message.from_user.id}: {discount_percent_str}")
    await state.set_state(PromotionForm.waiting_for_promo_code)
    await message.answer(
        "Введите промокод акции:",
        reply_markup=res_admin_cancel_keyboard()
    )

@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_promo_code))
@resident_required
async def process_promotional_code_and_create(message: Message, state: FSMContext, bot: Bot):
    promotional_code = message.text.strip()
    if not promotional_code:
        logger.warning(f"User {message.from_user.id} provided empty promotion code")
        await message.answer(
            "Промокод акции не может быть пустой. Пожалуйста, введите промокод:",
            reply_markup=res_admin_cancel_keyboard()
        )
        return
    if not re.match(r'^[A-Z0-9]+$', promotional_code) or not re.search(r'\d', promotional_code):
        logger.warning(f"User {message.from_user.id} provided invalid promo code format: {promotional_code}")
        await message.answer(
            "Промокод должен содержать только заглавные буквы и цифры, а также включать хотя бы одну цифру. Пожалуйста, введите корректный промокод:",
            reply_markup=res_admin_cancel_keyboard(),
            parse_mode=None
        )
    await state.update_data(promotional_code=promotional_code)

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
        "promotional_code": data.get("promotional_code"),
        "discount_percent": data.get("discount_percent"),
    }
    photo_file_id = data.get("photo")

    created_promotion = await create_new_promotion(promotion_data, photo_file_id, resident_id, bot)
    if created_promotion:
        logger.info(f"Promotion created successfully for user_id={message.from_user.id}, title={promotion_data['title']}")
        caption = (
            f"Акция успешно создана!\n"
            f"Название: {promotion_data['title']}\n"
            f"Описание: {promotion_data['description']}\n"
            f"Дата начала: {format_datetime(promotion_data.get('start_date'))}\n"
            f"Дата окончания: {format_datetime(promotion_data.get('end_date'))}\n"
            f"Промокод: {promotion_data['promotional_code']}\n"
            f"Скидка:{promotion_data['discount_percent']}{'%'}\n"
            f"Ожидайте подтверждения от администратора."
        )

        photo_url = created_promotion.get("photo")
        if photo_url:
            await message.answer_photo(
                photo=photo_url,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=res_admin_promotion_keyboard(),
            )

        await state.clear()
        if resident_id:
            await state.update_data(resident_id=resident_id, resident_name=data.get("resident_name"))
    else:
        logger.error(f"Failed to create promotion for user_id={message.from_user.id}")
        await message.answer(
            "Произошла ошибка при создании акции. Пожалуйста, проверьте данные и попробуйте еще раз.",
            reply_markup=res_admin_promotion_keyboard()
        )
        await state.clear()
        if resident_id:
            await state.update_data(resident_id=resident_id, resident_name=data.get("resident_name"))

# =================================================================================================
# Обработчики календаря и времени
# =================================================================================================

@RA_promotion_router.callback_query(F.data == "ignore")
@resident_required
async def process_ignore_callback(callback: CallbackQuery):
    logger.debug(f"Ignore callback received from user {callback.from_user.id}")
    await callback.answer()

@RA_promotion_router.callback_query(F.data.startswith("promo_select_date:"))
@resident_required
async def process_date_callback(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.debug(f"Processing date callback, state={current_state}, callback_data={callback.data}, user_id={callback.from_user.id}")

    date_str = callback.data[len("promo_select_date:"):]
    try:
        selected_date = datetime.strptime(date_str, "%d.%m.%Y").replace(tzinfo=MOSCOW_TZ)
        data = await state.get_data()
        updated_fields = data.get("updated_fields", {})

        if current_state == PromotionForm.waiting_for_start_date.state:
            await state.update_data(start_date=selected_date)
            await state.set_state(PromotionForm.waiting_for_start_time)
            await callback.message.edit_text(
                f"Выбрана дата начала: {date_str}. Выберите время начала:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
        elif current_state == PromotionForm.waiting_for_end_date.state:
            start_date = data.get("start_date")
            if selected_date.date() < start_date.date():
                logger.warning(f"End date {date_str} before start date")
                current_text = callback.message.text or ""
                new_text = "Дата окончания не может быть раньше даты начала. Выберите другую дату:"
                if current_text != new_text:
                    await callback.message.edit_text(
                        new_text,
                        reply_markup=get_calendar(prefix="promo_")
                    )
                else:
                    await callback.answer("Дата окончания не может быть раньше даты начала.")
                return
            await state.update_data(end_date=selected_date)
            await state.set_state(PromotionForm.waiting_for_end_time)
            await callback.message.edit_text(
                f"Выбрана дата окончания: {date_str}. Выберите время окончания:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
        elif current_state == PromotionEditForm.waiting_for_start_date.state:
            updated_fields["start_date"] = selected_date
            await state.update_data(start_date=selected_date, updated_fields=updated_fields)
            await state.set_state(PromotionEditForm.waiting_for_start_time)
            await callback.message.edit_text(
                f"Выбрана дата начала: {date_str}. Выберите время начала:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
        elif current_state == PromotionEditForm.waiting_for_end_date.state:
            start_date = data.get("start_date") or datetime.fromisoformat(data.get("promotion")["start_date"].replace("Z", "+03:00"))
            start_date = start_date.date() if isinstance(start_date, datetime) else start_date
            if selected_date.date() < start_date:
                logger.warning(f"End date {date_str} before start date {start_date}")
                current_text = callback.message.text or ""
                new_text = "Дата окончания не может быть раньше даты начала. Выберите другую дату:"
                if current_text != new_text:
                    await callback.message.edit_text(
                        new_text,
                        reply_markup=get_calendar(prefix="promo_")
                    )
                else:
                    await callback.answer("Дата окончания не может быть раньше даты начала.")
                return
            updated_fields["end_date"] = selected_date
            await state.update_data(end_date=selected_date, updated_fields=updated_fields)
            await state.set_state(PromotionEditForm.waiting_for_end_time)
            await callback.message.edit_text(
                f"Выбрана дата окончания: {date_str}. Выберите время окончания:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
    except ValueError as e:
        logger.error(f"Invalid date format: {date_str}, error: {e}")
        current_text = callback.message.text or ""
        new_text = "Ошибка в формате даты. Попробуйте снова:"
        if current_text != new_text:
            await callback.message.edit_text(
                new_text,
                reply_markup=get_calendar(prefix="promo_")
            )
        else:
            await callback.answer("Ошибка в формате даты.")
    except Exception as e:
        logger.error(f"Unexpected error in date callback: {e}")
        current_text = callback.message.text or ""
        new_text = "Произошла ошибка при выборе даты. Попробуйте снова:"
        if current_text != new_text:
            await callback.message.edit_text(
                new_text,
                reply_markup=get_calendar(prefix="promo_")
            )
        else:
            await callback.answer("Произошла ошибка при выборе даты.")
    await callback.answer()

@RA_promotion_router.callback_query(F.data.startswith(("promo_prev_month:", "promo_next_month:")))
@resident_required
async def process_month_navigation(callback: CallbackQuery, state: FSMContext):
    _, month, year = callback.data.split(":")
    month, year = int(month), int(year)
    await callback.message.edit_reply_markup(reply_markup=get_calendar(year, month, prefix="promo_"))
    await callback.answer()

@RA_promotion_router.callback_query(F.data == "promo_manual_time")
@resident_required
async def process_manual_time_request(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    prompt = "Введите время начала (формат ЧЧ:ММ, например, 15:30):" if current_state in (PromotionForm.waiting_for_start_time.state, PromotionEditForm.waiting_for_start_time.state) else "Введите время окончания (формат ЧЧ:ММ, например, 15:30):"
    await callback.message.edit_text(prompt)
    await callback.answer()

@RA_promotion_router.callback_query(F.data.startswith("promo_select_time:"))
@resident_required
async def process_time_callback(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.debug(f"Processing time callback, state={current_state}, callback_data={callback.data}, user_id={callback.from_user.id}")

    time_str = callback.data[len("promo_select_time:"):]
    try:
        if len(time_str) == 1 or (len(time_str) == 2 and time_str.isdigit()):
            time_str = f"{time_str.zfill(2)}:00"
        datetime.strptime(time_str, "%H:%M")
        data = await state.get_data()
        updated_fields = data.get("updated_fields", {})

        if current_state == PromotionForm.waiting_for_start_time.state:
            start_date = data.get("start_date")
            start_datetime = datetime.strptime(f"{start_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            if start_datetime < datetime.now(MOSCOW_TZ):
                logger.warning(f"Selected past start time: {time_str}")
                current_text = callback.message.text or ""
                new_text = "Время начала не может быть в прошлом. Выберите другое время:"
                if current_text != new_text:
                    await callback.message.edit_text(
                        new_text,
                        reply_markup=get_time_keyboard(prefix="promo_")
                    )
                else:
                    await callback.answer("Время начала не может быть в прошлом.")
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
                logger.warning(f"End time {time_str} not after start time")
                current_text = callback.message.text or ""
                new_text = "Время окончания должно быть позже времени начала. Выберите другое время:"
                if current_text != new_text:
                    await callback.message.edit_text(
                        new_text,
                        reply_markup=get_time_keyboard(prefix="promo_")
                    )
                else:
                    await callback.answer("Время окончания должно быть позже времени начала.")
                return
            await state.update_data(end_datetime=end_datetime)
            await state.set_state(PromotionForm.waiting_for_discount_percent)
            await callback.message.answer(
                f"Время окончания ({time_str}) сохранено. Введите скидку акции:",
                reply_markup=res_admin_edit_promotion_keyboard()
            )
        elif current_state == PromotionEditForm.waiting_for_start_time.state:
            start_date = data.get("start_date")
            start_datetime = datetime.strptime(f"{start_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            if start_datetime < datetime.now(MOSCOW_TZ):
                current_text = callback.message.text or ""
                new_text = "Время начала не может быть в прошлом. Выберите другое:"
                if current_text != new_text:
                    await callback.message.edit_text(
                        new_text,
                        reply_markup=get_time_keyboard(prefix="promo_")
                    )
                else:
                    await callback.answer("Время начала не может быть в прошлом.")
                return
            updated_fields["start_datetime"] = start_datetime
            await state.update_data(start_datetime=start_datetime, updated_fields=updated_fields)
            await state.set_state(PromotionEditForm.waiting_for_end_date)
            await callback.message.delete()
            await callback.message.answer(
                f"Время начала ({time_str}) сохранено. Выберите дату окончания (или нажмите 'Пропустить'):",
                reply_markup=get_calendar(prefix="promo_")
            )
        elif current_state == PromotionEditForm.waiting_for_end_time.state:
            end_date = data.get("end_date")
            end_datetime = datetime.strptime(f"{end_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            start_datetime = data.get("start_datetime") or datetime.fromisoformat(data.get("promotion")["start_date"].replace("Z", "+03:00"))
            if end_datetime <= start_datetime:
                current_text = callback.message.text or ""
                new_text = "Время окончания должно быть позже начала. Выберите другое:"
                if current_text != new_text:
                    await callback.message.edit_text(
                        new_text,
                        reply_markup=get_time_keyboard(prefix="promo_")
                    )
                else:
                    await callback.answer("Время окончания должно быть позже начала.")
                return
            updated_fields["end_datetime"] = end_datetime
            await state.update_data(end_datetime=end_datetime, updated_fields=updated_fields)
            await state.set_state(PromotionEditForm.waiting_for_discount_percent)
            await callback.message.answer(
                f"Время окончания ({time_str}) сохранено. Введите скидку акции (или нажмите 'Пропустить'):",
                reply_markup=res_admin_edit_promotion_keyboard()
            )
    except ValueError as e:
        logger.error(f"Invalid time format: {time_str}, error: {e}")
        current_text = callback.message.text or ""
        new_text = f"Неверный формат времени: '{time_str}'. Выберите время в формате ЧЧ:ММ (например, 22:00):"
        if current_text != new_text:
            await callback.message.edit_text(
                new_text,
                reply_markup=get_time_keyboard(prefix="promo_")
            )
        else:
            await callback.answer("Неверный формат времени.")
    except Exception as e:
        logger.error(f"Unexpected error in time callback: {e}")
        current_text = callback.message.text or ""
        new_text = "Произошла ошибка при выборе времени. Попробуйте снова:"
        if current_text != new_text:
            await callback.message.edit_text(
                new_text,
                reply_markup=get_time_keyboard(prefix="promo_")
            )
        else:
            await callback.answer("Произошла ошибка при выборе времени.")
    await callback.answer()

@RA_promotion_router.message(F.text.regexp(TIME_PATTERN), StateFilter(PromotionForm.waiting_for_start_time, PromotionEditForm.waiting_for_start_time))
@resident_required
async def process_manual_start_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    try:
        hours, minutes = map(int, TIME_PATTERN.match(time_str).groups())
        if hours > 23 or minutes > 59:
            logger.warning(f"User {message.from_user.id} provided out-of-range time: {time_str}")
            await message.answer(
                "Часы должны быть от 0 до 23, минуты от 00 до 59. Введите корректное время:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
            return
        time_str = f"{hours:02d}:{minutes:02d}"
        data = await state.get_data()
        start_date = data.get("start_date") or (data.get("updated_fields", {}).get("start_datetime") or datetime.now(MOSCOW_TZ)).date()
        start_datetime = datetime.strptime(f"{start_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
        
        if start_datetime < datetime.now(MOSCOW_TZ):
            logger.warning(f"User {message.from_user.id} selected past start time: {time_str}")
            await message.answer(
                "Время начала не может быть в прошлом. Введите другое время:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
            return
        
        logger.info(f"User {message.from_user.id} selected start_datetime: {start_datetime}")
        updated_fields = data.get("updated_fields", {})
        updated_fields["start_datetime"] = start_datetime
        await state.update_data(start_datetime=start_datetime, updated_fields=updated_fields)
        current_state = await state.get_state()
        next_state = PromotionForm.waiting_for_end_date if current_state.startswith("PromotionForm") else PromotionEditForm.waiting_for_end_date
        await state.set_state(next_state)
        await message.delete()
        await message.answer(
            f"Время начала ({time_str}) сохранено. Выберите дату окончания" + 
            (" (или нажмите 'Пропустить')" if current_state.startswith("PromotionEditForm") else ":"),
            reply_markup=get_calendar(prefix="promo_")
        )
    except ValueError:
        logger.error(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="promo_")
        )

@RA_promotion_router.message(F.text.regexp(TIME_PATTERN), StateFilter(PromotionForm.waiting_for_end_time, PromotionEditForm.waiting_for_end_time))
@resident_required
async def process_manual_end_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    try:
        hours, minutes = map(int, TIME_PATTERN.match(time_str).groups())
        if hours > 23 or minutes > 59:
            logger.warning(f"User {message.from_user.id} provided out-of-range time: {time_str}")
            await message.answer(
                "Часы должны быть от 0 до 23, минуты от 00 до 59. Введите корректное время:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
            return
        time_str = f"{hours:02d}:{minutes:02d}"
        data = await state.get_data()
        end_date = data.get("end_date") or (data.get("updated_fields", {}).get("end_datetime") or datetime.now(MOSCOW_TZ)).date()
        end_datetime = datetime.strptime(f"{end_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
        start_datetime = data.get("start_datetime") or (data.get("updated_fields", {}).get("start_datetime") or datetime.now(MOSCOW_TZ))
        
        if end_datetime <= start_datetime:
            logger.warning(f"User {message.from_user.id} selected end time {time_str} not after start time")
            await message.answer(
                "Время окончания должно быть позже времени начала. Введите другое время:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
            return
        
        logger.info(f"User {message.from_user.id} selected end_datetime: {end_datetime}")
        updated_fields = data.get("updated_fields", {})
        updated_fields["end_datetime"] = end_datetime
        await state.update_data(end_datetime=end_datetime, updated_fields=updated_fields)
        current_state = await state.get_state()
        next_state = PromotionForm.waiting_for_discount_percent if current_state.startswith("PromotionForm") else PromotionEditForm.waiting_for_discount_percent
        await state.set_state(next_state)
        await message.answer(
            f"Время окончания ({time_str}) сохранено. Введите скидку акции" + 
            (" (или нажмите 'Пропустить')" if current_state.startswith("PromotionEditForm") else ":"),
            reply_markup=res_admin_edit_promotion_keyboard() if current_state.startswith("PromotionEditForm") else None
        )
    except ValueError:
        logger.error(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="promo_")
        )
# =================================================================================================
# Обработчики редактирования акций
# =================================================================================================
@RA_promotion_router.message(F.text == "Изменить акцию")
@resident_required
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

@RA_promotion_router.message(F.text.startswith("🖋️ "))
@resident_required
async def edit_promotion_select(message: Message, state: FSMContext):
    promotion_title = message.text[2:].strip()
    promotion = await get_promotion_by_title(promotion_title, state)

    if not promotion:
        logger.warning(f"Promotion {promotion_title} not found for user_id={message.from_user.id}")
        await message.answer("Не удалось найти акцию.")
        return

    data = await state.get_data()
    resident_id = data.get("resident_id")
    resident_name = data.get("resident_name")
    await state.clear()
    await state.update_data(resident_id=resident_id, resident_name=resident_name, promotion=promotion, updated_fields={})
    await state.set_state(PromotionEditForm.waiting_for_title)

    current_promotion_text = (
        f"Название: {promotion['title']}\n"
        f"Описание: {promotion['description']}\n"
        f"Дата начала: {format_datetime(promotion.get('start_date'))}\n"
        f"Дата окончания: {format_datetime(promotion.get('end_date'))}\n"
        f"Промокод: {promotion['promotional_code']}\n"
        f"Скидка:{promotion['discount_percent']}{'%'}\n"
    )

    photo_url = promotion.get("photo")
    if photo_url:
        try:
            await message.answer_photo(
                photo=photo_url,
                caption=f"Вы выбрали акцию:\n\n{current_promotion_text}\n\nВведите новое название (или нажмите 'Пропустить' для сохранения текущего):",
                parse_mode="Markdown",
                reply_markup=res_admin_edit_promotion_keyboard()
            )
        except Exception as e:
            logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
            await message.answer(
                f"Вы выбрали акцию:\n\n{current_promotion_text}\n\n(Фото недоступно)\n\nВведите новое название (или нажмите 'Пропустить' для сохранения текущего):",
                reply_markup=res_admin_edit_promotion_keyboard()
            )
    else:
        await message.answer(
            f"Вы выбрали акцию:\n\n{current_promotion_text}\n\n(Фото отсутствует)\n\nВведите новое название (или нажмите 'Пропустить' для сохранения текущего):",
            reply_markup=res_admin_edit_promotion_keyboard()
        )

@RA_promotion_router.message(F.text.lower() == "пропустить")
@resident_required
async def skip_edit_field(message: Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()

    next_prompt_map = {
        PromotionEditForm.waiting_for_title.state: ("Отправьте новое фото", PromotionEditForm.waiting_for_photo),
        PromotionEditForm.waiting_for_photo.state: ("Введите новое описание", PromotionEditForm.waiting_for_description),
        PromotionEditForm.waiting_for_description.state: ("Выберите новую дату начала", PromotionEditForm.waiting_for_start_date),
        PromotionEditForm.waiting_for_start_date.state: ("Введите новое время начала", PromotionEditForm.waiting_for_start_time),
        PromotionEditForm.waiting_for_start_time.state: ("Выберите дату окончания", PromotionEditForm.waiting_for_end_date),
        PromotionEditForm.waiting_for_end_date.state: ("Введите время окончания", PromotionEditForm.waiting_for_end_time),
        PromotionEditForm.waiting_for_end_time.state: ("Введите скидку", PromotionEditForm.waiting_for_discount_percent),
        PromotionEditForm.waiting_for_discount_percent.state: ("Введите промокод", PromotionEditForm.waiting_for_promo_code),
    }

    if current_state in next_prompt_map:
        next_prompt, next_state = next_prompt_map[current_state]
        await state.set_state(next_state)
        if next_state in {PromotionEditForm.waiting_for_start_date, PromotionEditForm.waiting_for_end_date}:
            await message.answer(f"{next_prompt} (или нажмите 'Пропустить')", reply_markup=get_calendar(prefix="promo_"))
        elif next_state in {PromotionEditForm.waiting_for_start_time, PromotionEditForm.waiting_for_end_time}:
            await message.answer(f"{next_prompt} (или нажмите 'Пропустить')", reply_markup=get_time_keyboard(prefix="promo_"))
        else:
            await message.answer(f"{next_prompt} (или нажмите 'Пропустить')", reply_markup=res_admin_edit_promotion_keyboard())
        return

    elif current_state == PromotionEditForm.waiting_for_promo_code.state:
        return await skip_promotional_code(message, state, bot=bot)

    await message.answer("Невозможно пропустить этот шаг.")

@RA_promotion_router.message(PromotionEditForm.waiting_for_title)
@resident_required
async def process_promotion_title(message: Message, state: FSMContext):
    new_title = message.text.strip()
    if not new_title:
        await message.answer("Название не может быть пустым.", reply_markup=res_admin_edit_promotion_keyboard())
        return

    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        await handle_missing_promotion(message, state)
        return

    updated_fields = data.get("updated_fields", {})
    updated_fields["title"] = new_title
    await state.update_data(updated_fields=updated_fields)
    await state.set_state(PromotionEditForm.waiting_for_photo)
    await message.answer("Отправьте новое фото (или нажмите 'Пропустить'):", reply_markup=res_admin_edit_promotion_keyboard())

@RA_promotion_router.message(PromotionEditForm.waiting_for_photo)
@resident_required
async def process_promotion_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        await handle_missing_promotion(message, state)
        return

    is_valid, result = await validate_photo(message)
    if not is_valid:
        await message.answer(result, reply_markup=res_admin_edit_promotion_keyboard())
        return

    updated_fields = data.get("updated_fields", {})
    updated_fields["photo"] = result
    await state.update_data(updated_fields=updated_fields)
    await state.set_state(PromotionEditForm.waiting_for_description)
    await message.answer("Введите новое описание (или нажмите 'Пропустить'):", reply_markup=res_admin_edit_promotion_keyboard())

@RA_promotion_router.message(PromotionEditForm.waiting_for_description)
@resident_required
async def process_promotion_description(message: Message, state: FSMContext):
    new_description = message.text.strip()
    if not new_description:
        await message.answer("Описание не может быть пустым.", reply_markup=res_admin_edit_promotion_keyboard())
        return

    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        await handle_missing_promotion(message, state)
        return

    updated_fields = data.get("updated_fields", {})
    updated_fields["description"] = new_description
    await state.update_data(updated_fields=updated_fields)
    await state.set_state(PromotionEditForm.waiting_for_start_date)
    await message.answer("Выберите новую дату начала (или нажмите 'Пропустить'):", reply_markup=get_calendar(prefix="promo_"))

@RA_promotion_router.message(PromotionEditForm.waiting_for_discount_percent)
@resident_required
async def process_promotion_discount_percent(message: Message, state: FSMContext):
    discount_input = message.text.strip()
    try:
        discount_percent = Decimal(discount_input)
        if discount_percent < 0 or discount_percent > 100:
            logger.warning(f"User {message.from_user.id} provided invalid discount percent: {discount_input}")
            await message.answer(
                "Процент скидки должен быть в диапазоне от 0 до 100. Пожалуйста, введите корректный процент:",
                reply_markup=res_admin_edit_promotion_keyboard(),
                parse_mode=None
            )
            return
        if discount_percent.as_tuple().exponent < -2:
            logger.warning(f"User {message.from_user.id} provided too many decimal places: {discount_input}")
            await message.answer(
                "Процент скидки должен иметь не более двух знаков после запятой (например, 10 или 10.50):",
                reply_markup=res_admin_edit_promotion_keyboard(),
                parse_mode=None
            )
            return
        discount_percent_str = f"{discount_percent:.2f}"
    except ValueError:
        logger.warning(f"User {message.from_user.id} provided non-numeric discount percent: {discount_input}")
        await message.answer(
            "Пожалуйста, введите число для процента скидки (например, 10 или 10.50):",
            reply_markup=res_admin_edit_promotion_keyboard(),
            parse_mode=None
        )
        return
    data = await state.get_data()
    updated_fields = data.get("updated_fields", {})
    updated_fields["discount_percent"] = discount_percent_str
    await state.update_data(updated_fields=updated_fields)
    logger.info(f"Discount percent saved for user {message.from_user.id}: {discount_percent_str}")
    await state.set_state(PromotionEditForm.waiting_for_promo_code)
    await message.answer("Введите новый промокод (или нажмите 'Пропустить'):", reply_markup=res_admin_edit_promotion_keyboard())


@RA_promotion_router.message(PromotionEditForm.waiting_for_promo_code)
@resident_required
async def process_promotional_code(message: Message, state: FSMContext, bot: Bot):
    new_code = message.text.strip()
    if not new_code:
        await message.answer(
            "Промокод акции не может быть пустой. Пожалуйста, введите промокод:",
            reply_markup=res_admin_cancel_keyboard()
        )
        return
    if not re.match(r'^[A-Z0-9]+$', new_code) or not re.search(r'\d', new_code):
        logger.warning(f"User {message.from_user.id} provided invalid promo code format: {new_code}")
        await message.answer(
            "Промокод должен содержать только заглавные буквы и цифры, а также включать хотя бы одну цифру...",
            reply_markup=res_admin_cancel_keyboard(),
            parse_mode=None
        )
        return
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        await handle_missing_promotion(message, state)
        return
    updated_fields = data.get("updated_fields", {})
    updated_fields["promotional_code"] = new_code
    if "start_datetime" in updated_fields:
        updated_fields["start_date"] = updated_fields.pop("start_datetime").isoformat()
    if "end_datetime" in updated_fields:
        updated_fields["end_date"] = updated_fields.pop("end_datetime").isoformat()
    for field in ["title", "description", "start_date", "end_date", "promotional_code"]:
        if field not in updated_fields:
            updated_fields[field] = promotion[field]
    updated_fields = {k: v for k, v in updated_fields.items() if v is not None}
    if not updated_fields:
        logger.warning(f"No valid fields to update for promotion {promotion['id']}")
        await message.answer("Нет изменений для сохранения.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        await state.update_data(resident_id=data.get("resident_id"), resident_name=data.get("resident_name"))
        return
    updated_promotion = await update_promotion(promotion["id"], updated_fields, bot=bot)
    await finish_edit_promotion(message, state, updated_promotion, promotion, data)

@RA_promotion_router.message(PromotionEditForm.waiting_for_promo_code, F.text == "Пропустить")
@resident_required
async def skip_promotional_code(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    promotion = data.get("promotion")
    resident_id = data.get("resident_id")
    resident_name = data.get("resident_name")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await state.clear()
        if resident_id:
            await state.update_data(resident_id=resident_id, resident_name=resident_name)
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        return
    updated_fields = data.get("updated_fields", {})
    if "start_datetime" in updated_fields:
        updated_fields["start_date"] = updated_fields.pop("start_datetime").isoformat()
    if "end_datetime" in updated_fields:
        updated_fields["end_date"] = updated_fields.pop("end_datetime").isoformat()
    # Добавляем текущие значения обязательных полей
    for field in ["title", "description", "start_date", "end_date", "promotional_code"]:
        if field not in updated_fields:
            updated_fields[field] = promotion[field]
    # Удаляем None значения
    updated_fields = {k: v for k, v in updated_fields.items() if v is not None}
    if not updated_fields:
        logger.warning(f"No valid fields to update for promotion {promotion['id']}")
        await message.answer("Нет изменений для сохранения.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        if resident_id:
            await state.update_data(resident_id=resident_id, resident_name=resident_name)
        return
    updated_promotion = await update_promotion(promotion_id=promotion["id"], updated_fields=updated_fields, bot=bot)
    if updated_promotion:
        logger.info(f"Promotion {promotion['id']} updated successfully with fields: {updated_fields}")
        await state.update_data(promotion=updated_promotion)
        text = format_promotion_text(updated_promotion)
    else:
        logger.error(f"Failed to update promotion {promotion['id']}, updated_fields={updated_fields}")
        await message.answer("Ошибка при обновлении акции. Попробуйте снова.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        if resident_id:
            await state.update_data(resident_id=resident_id, resident_name=resident_name)
        return
    photo_url = updated_promotion.get("photo")
    if photo_url:
        try:
            await message.answer_photo(
                photo=photo_url,
                caption=f"{text}\n\nРедактирование завершено. Ожидайте подтверждения администратора.",
                parse_mode="HTML",
                reply_markup=res_admin_promotion_keyboard()
            )
        except Exception as e:
            logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
            await message.answer(
                f"{text}\n\n(Фото недоступно)\n\nРедактирование завершено. Ожидайте подтверждения администратора.",
                parse_mode="HTML",
                reply_markup=res_admin_promotion_keyboard()
            )
    else:
        await message.answer(
            f"{text}\n\n(Фото отсутствует)\n\nРедактирование завершено. Ожидайте подтверждения администратора.",
            parse_mode="HTML",
            reply_markup=res_admin_promotion_keyboard()
        )
    await state.set_state(PromotionEditForm.waiting_for_title)

# =================================================================================================
# Обработчики удаления акций
# =================================================================================================

@RA_promotion_router.message(F.text == "Удалить акцию")
@resident_required
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
        builder.button(text=f"🗑 {title}")
    builder.button(text="↩ Обратно")
    builder.adjust(1)

    await message.answer(
        "Выберите акцию для удаления:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@RA_promotion_router.message(F.text.startswith("🗑 "))
@resident_required
async def delete_promotion_select(message: Message, state: FSMContext):
    promotion_title = message.text[2:].strip()
    promotion = await get_promotion_by_title(promotion_title, state)
    if not promotion:
        logger.warning(f"Promotion {promotion_title} not found for user_id={message.from_user.id}")
        await message.answer("Не удалось найти акцию.")
        return

    data = await state.get_data()
    resident_id = data.get("resident_id")
    resident_name = data.get("resident_name")
    await state.clear()
    await state.update_data(resident_id=resident_id, resident_name=resident_name, promotion=promotion)
    await state.set_state(DeletePromotionForm.waiting_for_confirmation)

    current_promotion_text = (
        f"Название: {promotion['title']}\n"
        f"Описание: {promotion['description']}\n"
        f"Дата начала: {format_datetime(promotion.get('start_date'))}\n"
        f"Дата окончания: {format_datetime(promotion.get('end_date'))}\n"
        f"Промокод: {promotion['promotional_code']}\n"
        f"Скидка: {promotion['discount_percent']}\n"
    )

    builder = ReplyKeyboardBuilder()
    builder.button(text="Убрать")
    builder.button(text="Сбросить")
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
                f"Вы выбрали акцию:\n{current_promotion_text}\n\n(Фото недоступно)\n\nВы действительно хотите удалить эту акцию?",
                reply_markup=builder.as_markup(resize_keyboard=True)
            )
    else:
        await message.answer(
            f"Вы выбрали акцию:\n\n{current_promotion_text}\n\n(Фото отсутствует)\n\nВы действительно хотите удалить эту акцию?",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )

@RA_promotion_router.message(F.text == "Убрать", StateFilter(DeletePromotionForm.waiting_for_confirmation))
@resident_required
async def confirm_delete_promotion(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    resident_id = data.get("resident_id")
    resident_name = data.get("resident_name")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await state.clear()
        if resident_id:
            await state.update_data(resident_id=resident_id, resident_name=resident_name)
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
    if resident_id:
        await state.update_data(resident_id=resident_id, resident_name=resident_name)