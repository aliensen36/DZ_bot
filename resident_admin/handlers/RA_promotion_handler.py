import re
import aiohttp
import logging
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from data.config import config_settings
from data.url import url_promotions
from resident_admin.keyboards.res_admin_reply import res_admin_promotion_keyboard, res_admin_keyboard, res_admin_cancel_keyboard
from utils.filters import ChatTypeFilter
from utils.photo import download_photo_from_telegram, validate_photo
from utils.calendar import get_calendar, get_time_keyboard, format_datetime
from utils.constants import URL_PATTERN, MOSCOW_TZ, TIME_PATTERN
from resident_admin.services.resident_required import resident_required

# Настройка логирования
logger = logging.getLogger(__name__)

# Роутеры
RA_promotion_router = Router()
RA_promotion_router.message.filter(ChatTypeFilter("private"))
RA_bonus_router = Router()
RA_bonus_router.message.filter(ChatTypeFilter("private"))

# Константы
DISCOUNT_PATTERN = re.compile(r'^\s*скидка\s*(\d+\.?\d*)\s*%?\s*$', re.IGNORECASE)
BONUS_PATTERN = re.compile(r'^\s*бонус(?:ов)?\s*(\d+\.?\d*)\s*$', re.IGNORECASE)

# Состояния FSM
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

class DeletePromotionForm(StatesGroup):
    waiting_for_confirmation = State()

# Вспомогательные функции
def format_promotion_text(promotion: dict) -> str:
    return (
        f"<b>Акция обновлена: {promotion['title']}</b>\n\n"
        f"Описание: {promotion['description']}\n\n"
        f"Период: {format_datetime(promotion.get('start_date'))} - {format_datetime(promotion.get('end_date'))}\n\n"
        f"{promotion['discount_or_bonus'].capitalize()}: {promotion['discount_or_bonus_value']}{'%' if promotion['discount_or_bonus'] == 'скидка' else ''}\n\n"
        f"Ссылка: {promotion['url']}\n"
        f"Статус: {'Подтверждена' if promotion.get('is_approved', False) else 'Ожидает подтверждения'}"
    )

def get_edit_promotion_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Пропустить")
    builder.button(text="Сбросить")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

async def move_to_next_edit_state(state: FSMContext, current_state: str):
    edit_states = [
        PromotionEditForm.waiting_for_title,
        PromotionEditForm.waiting_for_photo,
        PromotionEditForm.waiting_for_description,
        PromotionEditForm.waiting_for_start_date,
        PromotionEditForm.waiting_for_start_time,
        PromotionEditForm.waiting_for_end_date,
        PromotionEditForm.waiting_for_end_time,
        PromotionEditForm.waiting_for_discount_or_bonus,
        PromotionEditForm.waiting_for_url
    ]
    current_index = [s.state for s in edit_states].index(current_state)
    next_index = (current_index + 1) % len(edit_states)
    next_state = edit_states[next_index]
    await state.set_state(next_state)
    return next_state

# Функции для работы с БД
async def create_new_promotion(promotion_data: dict, photo_file_id: str = None, resident_id: int = None, bot=None):
    logger.info(f"Creating promotion for resident_id={resident_id}")
    url = f"{url_promotions}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    data = promotion_data.copy()
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

# Обработчики меню и отмены
@RA_promotion_router.message(F.text == "Сбросить", StateFilter(PromotionForm, PromotionEditForm, DeletePromotionForm))
@resident_required
async def cancel_promotion_action(message: Message, state: FSMContext):
    logger.debug(f"Cancel action requested by user {message.from_user.id} in state {await state.get_state()}")
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=res_admin_promotion_keyboard()
    )

@RA_promotion_router.message(F.text == "↩ Обратно")
@resident_required
async def back_to_res_admin_menu(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} returned to admin menu")
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

# Обработчики создания акции
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
async def process_promotion_photo(message: Message, state: FSMContext):
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

@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_discount_or_bonus))
@resident_required
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

@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_url))
@resident_required
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
        caption = (
            f"Акция успешно создана!\n"
            f"Название: {promotion_data['title']}\n"
            f"Описание: {promotion_data['description']}\n"
            f"Дата начала: {format_datetime(promotion_data.get('start_date'))}\n"
            f"Дата окончания: {format_datetime(promotion_data.get('end_date'))}\n"
            f"Ссылка для участия: {promotion_data['url']}\n"
            f"{promotion_data['discount_or_bonus'].capitalize()}: {promotion_data['discount_or_bonus_value']}{'%' if promotion_data['discount_or_bonus'] == 'скидка' else ''}\n"
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
    else:
        logger.error(f"Failed to create promotion for user_id={message.from_user.id}")
        await message.answer(
            "Произошла ошибка при создании акции. Пожалуйста, проверьте данные и попробуйте еще раз.",
            reply_markup=res_admin_promotion_keyboard()
        )
        await state.clear()

# Обработчики календаря и времени
@RA_promotion_router.callback_query(F.data == "ignore")
@resident_required
async def process_ignore_callback(callback: CallbackQuery):
    logger.debug(f"Ignore callback received from user {callback.from_user.id}")
    await callback.answer()

@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_start_date))
@resident_required
async def process_start_date_selection(message: Message, state: FSMContext):
    await message.answer(
        "Выберите дату начала акции:",
        reply_markup=get_calendar(prefix="promo_")
    )

@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_end_date))
@resident_required
async def process_end_date_selection(message: Message, state: FSMContext):
    await message.answer(
        "Выберите дату окончания акции:",
        reply_markup=get_calendar(prefix="promo_")
    )

@RA_promotion_router.callback_query(F.data.startswith("promo_select_date:"))
@resident_required
async def process_date_callback(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.debug(f"Processing date callback, state={current_state}, callback_data={callback.data}, user_id={callback.from_user.id}")

    date_str = callback.data[len("promo_select_date:"):]
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

        if current_state in (PromotionForm.waiting_for_start_date.state, PromotionEditForm.waiting_for_start_date.state):
            await state.update_data(start_date=selected_date)
            await state.set_state(PromotionForm.waiting_for_start_time if current_state.startswith("PromotionForm") else PromotionEditForm.waiting_for_start_time)
            await callback.message.edit_text(
                f"Выбрана дата начала: {date_str}. Выберите время начала:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
        elif current_state in (PromotionForm.waiting_for_end_date.state, PromotionEditForm.waiting_for_end_date.state):
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
            await state.set_state(PromotionForm.waiting_for_end_time if current_state.startswith("PromotionForm") else PromotionEditForm.waiting_for_end_time)
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
    if current_state in (PromotionForm.waiting_for_start_time.state, PromotionEditForm.waiting_for_start_time.state):
        await callback.message.edit_text(
            "Введите время начала (формат ЧЧ:ММ, например, 15:30):",
        )
    elif current_state in (PromotionForm.waiting_for_end_time.state, PromotionEditForm.waiting_for_end_time.state):
        await callback.message.edit_text(
            "Введите время окончания (формат ЧЧ:ММ, например, 15:30):",
        )
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
        
        if current_state in (PromotionForm.waiting_for_start_time.state, PromotionEditForm.waiting_for_start_time.state):
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
            next_state = PromotionForm.waiting_for_end_date if current_state.startswith("PromotionForm") else PromotionEditForm.waiting_for_end_date
            await state.set_state(next_state)
            await callback.message.edit_text(
                f"Время начала ({time_str}) сохранено. Выберите дату окончания:",
                reply_markup=get_calendar(prefix="promo_")
            )
        elif current_state in (PromotionForm.waiting_for_end_time.state, PromotionEditForm.waiting_for_end_time.state):
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
            next_state = PromotionForm.waiting_for_discount_or_bonus if current_state.startswith("PromotionForm") else PromotionEditForm.waiting_for_discount_or_bonus
            await state.set_state(next_state)
            await callback.message.edit_text(
                f"Время окончания ({time_str}) сохранено. Введите скидку или бонус в формате 'Скидка 10%' или 'Бонусов 500':",
                reply_markup=get_edit_promotion_keyboard() if current_state.startswith("PromotionEditForm") else None
            )
    except ValueError:
        logger.error(f"User {callback.from_user.id} provided invalid time format: {time_str}")
        await callback.message.edit_text(
            f"Неверный формат времени: '{time_str}'. Пожалуйста, выберите время в формате ЧЧ:ММ (например, 22:00):",
            reply_markup=get_time_keyboard(prefix="promo_")
        )
    await callback.answer()

@RA_promotion_router.message(PromotionForm.waiting_for_start_time, PromotionEditForm.waiting_for_start_time)
@resident_required
async def process_manual_start_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    match = TIME_PATTERN.match(time_str)
    if not match:
        logger.warning(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="promo_")
        )
        return

    try:
        hours, minutes = map(int, match.groups())
        if hours > 23 or minutes > 59:
            logger.warning(f"User {message.from_user.id} provided out-of-range time: {time_str}")
            await message.answer(
                "Часы должны быть от 0 до 23, минуты от 00 до 59. Введите корректное время:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
            return
        time_str = f"{hours:02d}:{minutes:02d}"
        data = await state.get_data()
        start_date = data.get("start_date")
        start_datetime = datetime.strptime(f"{start_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
        
        if start_datetime < datetime.now(MOSCOW_TZ):
            logger.warning(f"User {message.from_user.id} selected past start time: {time_str}")
            await message.answer(
                "Время начала не может быть в прошлом. Введите другое время:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
            return
        
        await state.update_data(start_datetime=start_datetime)
        current_state = await state.get_state()
        next_state = PromotionForm.waiting_for_end_date if current_state.startswith("PromotionForm") else PromotionEditForm.waiting_for_end_date
        await state.set_state(next_state)
        await message.answer(
            f"Время начала ({time_str}) сохранено. Выберите дату окончания:",
            reply_markup=get_calendar(prefix="promo_")
        )
    except ValueError:
        logger.error(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="promo_")
        )

@RA_promotion_router.message(PromotionForm.waiting_for_end_time, PromotionEditForm.waiting_for_end_time)
@resident_required
async def process_manual_end_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    match = TIME_PATTERN.match(time_str)
    if not match:
        logger.warning(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="promo_")
        )
        return

    try:
        hours, minutes = map(int, match.groups())
        if hours > 23 or minutes > 59:
            logger.warning(f"User {message.from_user.id} provided out-of-range time: {time_str}")
            await message.answer(
                "Часы должны быть от 0 до 23, минуты от 00 до 59. Введите корректное время:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
            return
        time_str = f"{hours:02d}:{minutes:02d}"
        data = await state.get_data()
        end_date = data.get("end_date")
        end_datetime = datetime.strptime(f"{end_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
        start_datetime = data.get("start_datetime")
        
        if end_datetime <= start_datetime:
            logger.warning(f"User {message.from_user.id} selected end time {time_str} not after start time")
            await message.answer(
                "Время окончания должно быть позже времени начала. Введите другое время:",
                reply_markup=get_time_keyboard(prefix="promo_")
            )
            return
        
        await state.update_data(end_datetime=end_datetime)
        current_state = await state.get_state()
        next_state = PromotionForm.waiting_for_discount_or_bonus if current_state.startswith("PromotionForm") else PromotionEditForm.waiting_for_discount_or_bonus
        await state.set_state(next_state)
        await message.answer(
            f"Время окончания ({time_str}) сохранено. Введите скидку или бонус в формате 'Скидка 10%' или 'Бонусов 500':",
            reply_markup=get_edit_promotion_keyboard() if current_state.startswith("PromotionEditForm") else None
        )
    except ValueError:
        logger.error(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="promo_")
        )

# Обработчики редактирования акций
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

    await state.clear()
    await state.set_state(PromotionEditForm.waiting_for_title)
    await state.update_data(promotion=promotion)

    current_promotion_text = (
        f"Название: {promotion['title']}\n"
        f"Описание: Mantelpiece\n"
        f"Дата начала: {format_datetime(promotion.get('start_date'))}\n"
        f"Дата окончания: {format_datetime(promotion.get('end_date'))}\n"
        f"Ссылка для участия: {promotion['url']}\n"
        f"{promotion['discount_or_bonus'].capitalize()}: {promotion['discount_or_bonus_value']}{'%' if promotion['discount_or_bonus'] == 'скидка' else ''}\n"
    )

    photo_url = promotion.get("photo")
    if photo_url:
        try:
            await message.answer_photo(
                photo=photo_url,
                caption=f"Вы выбрали акцию:\n\n{current_promotion_text}\n\nВведите новое название (или нажмите 'Пропустить' для сохранения текущего):",
                parse_mode="Markdown",
                reply_markup=get_edit_promotion_keyboard()
            )
        except Exception as e:
            logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
            await message.answer(
                f"Вы выбрали акцию:\n\n{current_promotion_text}\n\n(Фото недоступно)\n\nВведите новое название (или нажмите 'Пропустить' для сохранения текущего):",
                reply_markup=get_edit_promotion_keyboard()
            )
    else:
        await message.answer(
            f"Вы выбрали акцию:\n\n{current_promotion_text}\n\n(Фото отсутствует)\n\nВведите новое название (или нажмите 'Пропустить' для сохранения текущего):",
            reply_markup=get_edit_promotion_keyboard()
        )

@RA_promotion_router.message(PromotionEditForm.waiting_for_title, F.text == "Пропустить")
@resident_required
async def skip_promotion_title(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return
    next_state = await move_to_next_edit_state(state, PromotionEditForm.waiting_for_title.state)
    await message.answer("Отправьте новое фото (или нажмите 'Пропустить' для сохранения текущего):", reply_markup=get_edit_promotion_keyboard())

@RA_promotion_router.message(PromotionEditForm.waiting_for_title)
@resident_required
async def process_promotion_title(message: Message, state: FSMContext):
    new_title = message.text.strip()
    if not new_title:
        logger.warning(f"User {message.from_user.id} provided empty title for update")
        await message.answer("Название не может быть пустым.", reply_markup=get_edit_promotion_keyboard())
        return
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return
    updated_promotion = await update_promotion(promotion_id=promotion["id"], updated_fields={"title": new_title}, bot=None)
    if updated_promotion:
        logger.info(f"Promotion {promotion['id']} title updated to '{new_title}'")
        await state.update_data(promotion=updated_promotion)
        text = format_promotion_text(updated_promotion)
        photo_url = updated_promotion.get("photo")
        if photo_url:
            try:
                await message.answer_photo(
                    photo=photo_url,
                    caption=f"{text}\n\nОтправьте новое фото (или нажмите 'Пропустить' для сохранения текущего):",
                    parse_mode="HTML",
                    reply_markup=get_edit_promotion_keyboard()
                )
            except Exception as e:
                logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
                await message.answer(
                    f"{text}\n\n(Фото недоступно)\n\nОтправьте новое фото (или нажмите 'Пропустить' для сохранения текущего):",
                    parse_mode="HTML",
                    reply_markup=get_edit_promotion_keyboard()
                )
        else:
            await message.answer(
                f"{text}\n\n(Фото отсутствует)\n\nОтправьте новое фото (или нажмите 'Пропустить' для сохранения текущего):",
                parse_mode="HTML",
                reply_markup=get_edit_promotion_keyboard()
            )
        await move_to_next_edit_state(state, PromotionEditForm.waiting_for_title.state)
    else:
        logger.error(f"Failed to update title for promotion {promotion['id']}")
        await message.answer("Ошибка при обновлении названия. Попробуйте снова.", reply_markup=get_edit_promotion_keyboard())

@RA_promotion_router.message(PromotionEditForm.waiting_for_photo, F.text == "Пропустить")
@resident_required
async def skip_promotion_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return
    next_state = await move_to_next_edit_state(state, PromotionEditForm.waiting_for_photo.state)
    await message.answer("Введите новое описание (или нажмите 'Пропустить' для сохранения текущего):", reply_markup=get_edit_promotion_keyboard())

@RA_promotion_router.message(PromotionEditForm.waiting_for_photo)
@resident_required
async def process_promotion_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return

    is_valid, result = await validate_photo(message)
    if not is_valid:
        await message.answer(result, reply_markup=get_edit_promotion_keyboard())
        return
    photo_file_id = result
    updated_promotion = await update_promotion(promotion_id=promotion["id"], updated_fields={"photo": photo_file_id}, bot=bot)
    if updated_promotion and isinstance(updated_promotion, dict):
        logger.info(f"Photo updated for promotion {promotion['id']}")
        await state.update_data(promotion=updated_promotion)
        text = format_promotion_text(updated_promotion)
        photo_url = updated_promotion.get("photo")
        if photo_url:
            try:
                await message.answer_photo(
                    photo=photo_url,
                    caption=f"{text}\n\nВведите новое описание (или нажмите 'Пропустить' для сохранения текущего):",
                    parse_mode="HTML",
                    reply_markup=get_edit_promotion_keyboard()
                )
            except Exception as e:
                logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
                await message.answer(
                    f"{text}\n\n(Фото недоступно)\n\nВведите новое описание (или нажмите 'Пропустить' для сохранения текущего):",
                    parse_mode="HTML",
                    reply_markup=get_edit_promotion_keyboard()
                )
        else:
            await message.answer(
                f"{text}\n\n(Фото отсутствует)\n\nВведите новое описание (или нажмите 'Пропустить' для сохранения текущего):",
                parse_mode="HTML",
                reply_markup=get_edit_promotion_keyboard()
            )
        await move_to_next_edit_state(state, PromotionEditForm.waiting_for_photo.state)
    else:
        logger.error(f"Failed to update photo for promotion {promotion['id']}")
        await message.answer("Ошибка при обновлении фото. Попробуйте снова.", reply_markup=get_edit_promotion_keyboard())

@RA_promotion_router.message(PromotionEditForm.waiting_for_description, F.text == "Пропустить")
@resident_required
async def skip_promotion_description(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return
    next_state = await move_to_next_edit_state(state, PromotionEditForm.waiting_for_description.state)
    await message.answer("Выберите новую дату начала (или нажмите 'Пропустить' для сохранения текущей):", reply_markup=get_calendar(prefix="promo_"))

@RA_promotion_router.message(PromotionEditForm.waiting_for_description)
@resident_required
async def process_promotion_description(message: Message, state: FSMContext):
    new_description = message.text.strip()
    if not new_description:
        logger.warning(f"User {message.from_user.id} provided empty description")
        await message.answer("Описание не может быть пустым.", reply_markup=get_edit_promotion_keyboard())
        return

    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return

    updated_promotion = await update_promotion(promotion_id=promotion["id"], updated_fields={"description": new_description})
    if updated_promotion:
        logger.info(f"Description updated for promotion {promotion['id']}")
        await state.update_data(promotion=updated_promotion)
        text = format_promotion_text(updated_promotion)
        photo_url = updated_promotion.get("photo")
        if photo_url:
            try:
                await message.answer_photo(
                    photo=photo_url,
                    caption=f"{text}\n\nВыберите новую дату начала (или нажмите 'Пропустить' для сохранения текущей):",
                    parse_mode="HTML",
                    reply_markup=get_calendar(prefix="promo_")
                )
            except Exception as e:
                logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
                await message.answer(
                    f"{text}\n\n(Фото недоступно)\n\nВыберите новую дату начала (или нажмите 'Пропустить' для сохранения текущей):",
                    parse_mode="HTML",
                    reply_markup=get_calendar(prefix="promo_")
                )
        else:
            await message.answer(
                f"{text}\n\n(Фото отсутствует)\n\nВыберите новую дату начала (или нажмите 'Пропустить' для сохранения текущей):",
                parse_mode="HTML",
                reply_markup=get_calendar(prefix="promo_")
            )
        await move_to_next_edit_state(state, PromotionEditForm.waiting_for_description.state)
    else:
        logger.error(f"Failed to update description for promotion {promotion['id']}")
        await message.answer("Ошибка при обновлении описания. Попробуйте снова.", reply_markup=get_edit_promotion_keyboard())

@RA_promotion_router.message(PromotionEditForm.waiting_for_start_date, F.text == "Пропустить")
@resident_required
async def skip_promotion_start_date(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return
    next_state = await move_to_next_edit_state(state, PromotionEditForm.waiting_for_start_date.state)
    await message.answer("Выберите новое время начала (или нажмите 'Пропустить' для сохранения текущего):", reply_markup=get_time_keyboard(prefix="promo_"))

@RA_promotion_router.message(PromotionEditForm.waiting_for_start_time, F.text == "Пропустить")
@resident_required
async def skip_promotion_start_time(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return
    next_state = await move_to_next_edit_state(state, PromotionEditForm.waiting_for_start_time.state)
    await message.answer("Выберите новую дату окончания (или нажмите 'Пропустить' для сохранения текущей):", reply_markup=get_calendar(prefix="promo_"))

@RA_promotion_router.message(PromotionEditForm.waiting_for_end_date, F.text == "Пропустить")
@resident_required
async def skip_promotion_end_date(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return
    next_state = await move_to_next_edit_state(state, PromotionEditForm.waiting_for_end_date.state)
    await message.answer("Выберите новое время окончания (или нажмите 'Пропустить' для сохранения текущего):", reply_markup=get_time_keyboard(prefix="promo_"))

@RA_promotion_router.message(PromotionEditForm.waiting_for_end_time, F.text == "Пропустить")
@resident_required
async def skip_promotion_end_time(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return
    next_state = await move_to_next_edit_state(state, PromotionEditForm.waiting_for_end_time.state)
    await message.answer(
        "Введите новую скидку или бонус в формате 'Скидка 10%' или 'Бонусов 500' (или нажмите 'Пропустить' для сохранения текущего):",
        reply_markup=get_edit_promotion_keyboard()
    )

@RA_promotion_router.message(PromotionEditForm.waiting_for_discount_or_bonus, F.text == "Пропустить")
@resident_required
async def skip_promotion_discount_or_bonus(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return
    next_state = await move_to_next_edit_state(state, PromotionEditForm.waiting_for_discount_or_bonus.state)
    await message.answer("Введите новую ссылку (или нажмите 'Пропустить' для сохранения текущей):", reply_markup=get_edit_promotion_keyboard())

@RA_promotion_router.message(PromotionEditForm.waiting_for_discount_or_bonus)
@resident_required
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
                reply_markup=get_edit_promotion_keyboard()
            )
            return
        updated_fields = {"discount_or_bonus": "скидка", "discount_or_bonus_value": discount_value}
    elif bonus_match:
        bonus_value = float(bonus_match.group(1))
        if bonus_value <= 0:
            logger.warning(f"User {message.from_user.id} provided invalid bonus value: {bonus_value}")
            await message.answer(
                "Значение бонуса должно быть больше 0. Введите корректное значение, например 'Бонусов 500':",
                reply_markup=get_edit_promotion_keyboard()
            )
            return
        updated_fields = {"discount_or_bonus": "бонус", "discount_or_bonus_value": bonus_value}
    else:
        logger.warning(f"User {message.from_user.id} provided invalid discount/bonus format: {input_text}")
        await message.answer(
            "Неверный формат. Введите 'Скидка 10%' или 'Бонусов 500':",
            reply_markup=get_edit_promotion_keyboard()
        )
        return

    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return

    updated_promotion = await update_promotion(promotion_id=promotion["id"], updated_fields=updated_fields)
    if updated_promotion:
        logger.info(f"Discount/bonus updated for promotion {promotion['id']}")
        await state.update_data(promotion=updated_promotion)
        text = format_promotion_text(updated_promotion)
        photo_url = updated_promotion.get("photo")
        if photo_url:
            try:
                await message.answer_photo(
                    photo=photo_url,
                    caption=f"{text}\n\nВведите новую ссылку (или нажмите 'Пропустить' для сохранения текущей):",
                    parse_mode="HTML",
                    reply_markup=get_edit_promotion_keyboard()
                )
            except Exception as e:
                logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
                await message.answer(
                    f"{text}\n\n(Фото недоступно)\n\nВведите новую ссылку (или нажмите 'Пропустить' для сохранения текущей):",
                    parse_mode="HTML",
                    reply_markup=get_edit_promotion_keyboard()
                )
        else:
            await message.answer(
                f"{text}\n\n(Фото отсутствует)\n\nВведите новую ссылку (или нажмите 'Пропустить' для сохранения текущей):",
                parse_mode="HTML",
                reply_markup=get_edit_promotion_keyboard()
            )
        await move_to_next_edit_state(state, PromotionEditForm.waiting_for_discount_or_bonus.state)
    else:
        logger.error(f"Failed to update discount/bonus for promotion {promotion['id']}")
        await message.answer(
            "Ошибка при обновлении скидки/бонуса. Попробуйте еще раз.",
            reply_markup=get_edit_promotion_keyboard()
        )

@RA_promotion_router.message(PromotionEditForm.waiting_for_url, F.text == "Пропустить")
@resident_required
async def skip_promotion_url(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return
    text = format_promotion_text(promotion)
    photo_url = promotion.get("photo")
    if photo_url:
        try:
            await message.answer_photo(
                photo=photo_url,
                caption=f"{text}\n\nРедактирование завершено. Начать заново с названия (или нажмите 'Сбросить' для выхода)?",
                parse_mode="HTML",
                reply_markup=get_edit_promotion_keyboard()
            )
        except Exception as e:
            logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
            await message.answer(
                f"{text}\n\n(Фото недоступно)\n\nРедактирование завершено. Начать заново с названия (или нажмите 'Сбросить' для выхода)?",
                parse_mode="HTML",
                reply_markup=get_edit_promotion_keyboard()
            )
    else:
        await message.answer(
            f"{text}\n\n(Фото отсутствует)\n\nРедактирование завершено. Начать заново с названия (или нажмите 'Сбросить' для выхода)?",
            parse_mode="HTML",
            reply_markup=get_edit_promotion_keyboard()
        )
    await state.set_state(PromotionEditForm.waiting_for_title)

@RA_promotion_router.message(PromotionEditForm.waiting_for_url)
@resident_required
async def process_promotion_url(message: Message, state: FSMContext):
    new_url = message.text.strip()
    if not new_url:
        logger.warning(f"User {message.from_user.id} provided empty URL")
        await message.answer("Ссылка не может быть пустой.", reply_markup=get_edit_promotion_keyboard())
        return
    if not URL_PATTERN.match(new_url):
        logger.warning(f"User {message.from_user.id} provided invalid URL format: {new_url}")
        await message.answer("Неверный формат ссылки. Пожалуйста, введите корректную ссылку:", reply_markup=get_edit_promotion_keyboard())
        return
    
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        logger.error(f"No promotion data found for user_id={message.from_user.id}")
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_promotion_keyboard())
        await state.clear()
        return

    updated_promotion = await update_promotion(promotion_id=promotion["id"], updated_fields={"url": new_url})
    if updated_promotion:
        logger.info(f"URL updated for promotion {promotion['id']}")
        await state.update_data(promotion=updated_promotion)
        text = format_promotion_text(updated_promotion)
        photo_url = updated_promotion.get("photo")
        if photo_url:
            try:
                await message.answer_photo(
                    photo=photo_url,
                    caption=f"{text}\n\nРедактирование завершено. Начать заново с названия (или нажмите 'Сбросить' для выхода)?",
                    parse_mode="HTML",
                    reply_markup=get_edit_promotion_keyboard()
                )
            except Exception as e:
                logger.error(f"Failed to send photo for promotion {promotion['id']}: {e}")
                await message.answer(
                    f"{text}\n\n(Фото недоступно)\n\nРедактирование завершено. Начать заново с названия (или нажмите 'Сбросить' для выхода)?",
                    parse_mode="HTML",
                    reply_markup=get_edit_promotion_keyboard()
                )
        else:
            await message.answer(
                f"{text}\n\n(Фото отсутствует)\n\nРедактирование завершено. Начать заново с названия (или нажмите 'Сбросить' для выхода)?",
                parse_mode="HTML",
                reply_markup=get_edit_promotion_keyboard()
            )
        await state.set_state(PromotionEditForm.waiting_for_title)
    else:
        logger.error(f"Failed to update URL for promotion {promotion['id']}")
        await message.answer("Ошибка при обновлении ссылки. Попробуйте снова.", reply_markup=get_edit_promotion_keyboard())

# Обработчики удаления акций
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

    await state.clear()
    await state.set_state(DeletePromotionForm.waiting_for_confirmation)
    await state.update_data(promotion=promotion)

    current_promotion_text = (
        f"Название: {promotion['title']}\n"
        f"Описание: {promotion['description']}\n"
        f"Дата начала: {format_datetime(promotion.get('start_date'))}\n"
        f"Дата окончания: {format_datetime(promotion.get('end_date'))}\n"
        f"Ссылка для участия: {promotion['url']}\n"
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
                f"Вы выбрали акцию:\n\n{current_promotion_text}\n\n(Фото недоступно)\n\nВы действительно хотите удалить эту акцию?",
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