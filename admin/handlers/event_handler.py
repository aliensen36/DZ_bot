import aiohttp
import re
import logging
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError
from aiogram.exceptions import TelegramBadRequest
from aiogram import Bot, F, Router
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ContentType
from aiogram.fsm.context import FSMContext
from data.config import config_settings
from admin.keyboards.admin_reply import events_management_keyboard, admin_keyboard, cancel_keyboard, edit_event_keyboard
from data.url import url_event
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID
from utils.dowload_photo import download_photo_from_telegram
from utils.calendar import get_calendar, get_time_keyboard

# Настройка логирования
logger = logging.getLogger(__name__)

admin_event_router = Router()
admin_event_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([ADMIN_CHAT_ID], show_message=False)
)

# Константы
URL_PATTERN = re.compile(
    r'^(https?://)?'
    r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
    r'(:\d+)?'
    r'(/[\w\-._~:/?#[\]@!$&\'()*+,;=]*)?$'
)
MOSCOW_TZ = timezone(timedelta(hours=3))
TIME_PATTERN = re.compile(r'^\s*(\d{1,2}):(\d{2})\s*$')
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png']

# =================================================================================================
# Состояния FSM
# =================================================================================================

class EventForm(StatesGroup):
    waiting_for_title = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_info = State()
    waiting_for_start_date = State()
    waiting_for_start_time = State()
    waiting_for_end_date = State()
    waiting_for_end_time = State()
    waiting_for_location = State()
    waiting_for_url = State()

class EditEventForm(StatesGroup):
    choosing_field = State()
    waiting_for_title = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_info = State()
    waiting_for_start_date = State()
    waiting_for_start_time = State()
    waiting_for_end_date = State()
    waiting_for_end_time = State()
    waiting_for_location = State()
    waiting_for_url = State()

class DeleteEventForm(StatesGroup):
    waiting_for_confirmation = State()

# =================================================================================================
# Утилитные функции
# =================================================================================================

# Форматирует строку ISO-даты в формат DD.MM.YYYY HH:MM
def format_datetime(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+03:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception as e:
        logger.error(f"Failed to format datetime: {dt_str}, error: {e}")
        return dt_str or "-"

# Проверяет, является ли сообщение фото, и соответствует ли оно требованиям (формат JPG/PNG, размер до 10MB)
async def validate_photo(message: Message) -> tuple[bool, str]:
    if message.content_type != ContentType.PHOTO:
        logger.warning(f"Invalid content type: {message.content_type}")
        return False, "Пожалуйста, отправьте изображение в формате JPG или PNG."
    if not message.photo:
        logger.warning("No photo received")
        return False, "Фото не получено. Пожалуйста, отправьте изображение."
    photo = message.photo[-1]
    if photo.file_size > MAX_PHOTO_SIZE:
        logger.warning(f"Photo size {photo.file_size} exceeds limit {MAX_PHOTO_SIZE}")
        return False, "Фото слишком большое. Максимальный размер: 10 МБ."
    return True, photo.file_id

# =================================================================================================
# Функции для работы с API
# =================================================================================================

# Создает новое мероприятие через API
async def create_new_event(event_data: dict, photo_file_id: str, bot: Bot) -> dict:
    url = f"{url_event}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    form_data = aiohttp.FormData()
    for key, value in event_data.items():
        form_data.add_field(key, str(value))

    try:
        photo_content = await download_photo_from_telegram(bot, photo_file_id)
        form_data.add_field(
            "photo",
            photo_content,
            filename=f"event_{datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')}.jpg",
            content_type="image/jpeg"
        )
    except Exception as e:
        logger.error(f"Failed to download photo: {e}")
        raise Exception(f"Не удалось загрузить фото: {str(e)}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=form_data) as response:
                if response.status == 201:
                    logger.info(f"Event created successfully: {event_data['title']}")
                    return await response.json()
                logger.error(f"Failed to create event, status={response.status}, body={await response.text()}")
                return None
    except aiohttp.ClientError as e:
        logger.error(f"Network error creating event: {e}")
        return None

# Получает список мероприятий через API
async def fetch_events() -> list:
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_event}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                logger.error(f"Failed to fetch events, status={resp.status}")
                return []
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching events: {e}")
        return []

# Ищет мероприятие по названию
async def get_event_by_title(title: str) -> dict:
    events = await fetch_events()
    for event in events:
        if event.get("title") == title:
            return event
    logger.warning(f"Event with title '{title}' not found")
    return None

# Обновляет мероприятие через API
async def update_event(event_id: int, updated_fields: dict, bot: Bot = None) -> dict:
    url = f"{url_event}{event_id}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    form_data = aiohttp.FormData()
    for key, value in updated_fields.items():
        if key == "photo" and value and bot:
            try:
                photo_content = await download_photo_from_telegram(bot, value)
                form_data.add_field(
                    "photo",
                    photo_content,
                    filename=f"event_{event_id}.jpg",
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
                    logger.info(f"Event {event_id} updated successfully")
                    return await response.json()
                logger.error(f"Failed to update event {event_id}, status={response.status}, body={await response.text()}")
                return None
    except Exception as e:
        logger.error(f"Error updating event {event_id}: {e}")
        return None

# Удаляет мероприятие через API
async def delete_event(event_id: int) -> bool:
    url = f"{url_event}{event_id}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as resp:
                if resp.status in (200, 204):
                    logger.info(f"Event {event_id} deleted successfully")
                    return True
                logger.error(f"Failed to delete event {event_id}, status={resp.status}")
                return False
    except Exception as e:
        logger.error(f"Error deleting event {event_id}: {e}")
        return False

# =================================================================================================
# Обработчики меню и отмены
# =================================================================================================

# Показывает меню управления мероприятиями
@admin_event_router.message(F.text == "🎉 Мероприятия")
async def handle_events(message: Message):
    await message.answer(
        "Управление мероприятиями:",
        reply_markup=events_management_keyboard()
    )

# Возвращает в главное меню администратора
@admin_event_router.message(F.text == "Назад")
async def back_to_admin_menu(message: Message):
    await message.answer(
        "Вы вернулись в главное меню администратора.",
        reply_markup=admin_keyboard()
    )

# Обрабатывает отмену создания, редактирования или удаления акции
@admin_event_router.message(F.text == "Отмена", StateFilter(EventForm, EditEventForm, DeleteEventForm))
async def cancel_promotion_action(message: Message, state: FSMContext):
    logger.debug(f"Cancel action requested by user {message.from_user.id} in state {await state.get_state()}")
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=events_management_keyboard()
    )

# =================================================================================================
# Обработчики создания мероприятия
# =================================================================================================

# Начинает процесс создания нового мероприятия
@admin_event_router.message(F.text == "Добавить мероприятие")
async def handle_add_event(message: Message, state: FSMContext):
    await state.set_state(EventForm.waiting_for_title)
    await message.answer(
        "Введите название мероприятия:",
        reply_markup=cancel_keyboard()
    )

# Обрабатывает название мероприятия
@admin_event_router.message(StateFilter(EventForm.waiting_for_title))
async def process_event_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым. Введите название:", reply_markup=cancel_keyboard())
        return
    await state.update_data(title=title)
    await state.set_state(EventForm.waiting_for_photo)
    await message.answer("Отправьте фото для мероприятия:", reply_markup=cancel_keyboard())

# Обрабатывает фото для мероприятия
@admin_event_router.message(StateFilter(EventForm.waiting_for_photo))
async def process_event_photo(message: Message, state: FSMContext):
    is_valid, result = await validate_photo(message)
    if not is_valid:
        await message.answer(result, reply_markup=cancel_keyboard())
        return
    photo_file_id = result
    await state.update_data(photo=photo_file_id)
    await state.set_state(EventForm.waiting_for_description)
    await message.answer("Фото получено. Введите описание мероприятия:", reply_markup=cancel_keyboard())

# Обрабатывает описание мероприятия
@admin_event_router.message(StateFilter(EventForm.waiting_for_description))
async def process_event_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if not description:
        await message.answer("Описание не может быть пустым. Введите описание:", reply_markup=cancel_keyboard())
        return
    await state.update_data(description=description)
    await state.set_state(EventForm.waiting_for_info)
    await message.answer("Введите дополнительную информацию о мероприятии:", reply_markup=cancel_keyboard())

# Обрабатывает дополнительную информацию о мероприятии
@admin_event_router.message(StateFilter(EventForm.waiting_for_info))
async def process_event_info(message: Message, state: FSMContext):
    info = message.text.strip()
    if not info:
        await message.answer("Информация не может быть пустой. Введите информацию:", reply_markup=cancel_keyboard())
        return
    await state.update_data(info=info)
    await state.set_state(EventForm.waiting_for_start_date)
    await message.answer("Выберите дату начала мероприятия:", reply_markup=get_calendar(prefix="event_"))

# Обрабатывает место проведения мероприятия
@admin_event_router.message(StateFilter(EventForm.waiting_for_location))
async def process_event_location(message: Message, state: FSMContext):
    location = message.text.strip()
    if not location:
        await message.answer("Место проведения не может быть пустым. Введите место:", reply_markup=cancel_keyboard())
        return
    await state.update_data(location=location)
    await state.set_state(EventForm.waiting_for_url)
    await message.answer("Введите ссылку для регистрации на мероприятие:", reply_markup=cancel_keyboard())

# Обрабатывает ссылку и создает мероприятие
@admin_event_router.message(StateFilter(EventForm.waiting_for_url))
async def process_event_url_and_create(message: Message, state: FSMContext, bot: Bot):
    url = message.text.strip()
    if not url:
        await message.answer("Ссылка не может быть пустой. Введите ссылку:", reply_markup=cancel_keyboard())
        return
    if not URL_PATTERN.match(url):
        logger.warning(f"Invalid URL: {url}")
        await message.answer("Неверный формат ссылки. Введите корректную ссылку:", reply_markup=cancel_keyboard())
        return
    await state.update_data(url=url)
    data = await state.get_data()
    event_data = {
        "title": data.get("title"),
        "description": data.get("description"),
        "info": data.get("info"),
        "start_date": data.get("start_datetime").isoformat(),
        "end_date": data.get("end_datetime").isoformat(),
        "location": data.get("location"),
        "url": data.get("url"),
    }
    photo_file_id = data.get("photo")

    try:
        created_event = await create_new_event(event_data, photo_file_id, bot)
        if created_event:
            caption = (
                f"Мероприятие успешно создано!\n"
                f"Название: {event_data['title']}\n"
                f"Описание: {event_data['description']}\n"
                f"Информация: {event_data['info']}\n"
                f"Дата начала: {format_datetime(event_data['start_date'])}\n"
                f"Дата окончания: {format_datetime(event_data['end_date'])}\n"
                f"Место: {event_data['location']}\n"
                f"Ссылка для регистрации: {event_data['url']}"
            )
            photo_url = created_event.get("photo")
            if photo_url:
                await message.answer_photo(
                    photo=photo_url,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=events_management_keyboard(),
                )
            else:
                await message.answer(caption, reply_markup=events_management_keyboard())
            await state.clear()
        else:
            logger.error(f"Failed to create event: {event_data['title']}")
            await message.answer(
                "Ошибка при создании мероприятия. Проверьте данные и попробуйте снова.",
                reply_markup=events_management_keyboard()
            )
            await state.clear()
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        await message.answer(
            f"Ошибка: {str(e)}. Попробуйте снова.",
            reply_markup=events_management_keyboard()
        )
        await state.clear()

# =================================================================================================
# Обработчики календаря и времени
# =================================================================================================

@admin_event_router.callback_query(F.data == "ignore")
async def process_ignore_callback(callback: CallbackQuery):
    logger.debug(f"Ignore callback received from user {callback.from_user.id}")
    await callback.answer()

# Запрашивает выбор даты начала
@admin_event_router.message(StateFilter(EventForm.waiting_for_start_date))
async def process_start_date_selection(message: Message, state: FSMContext):
    await message.answer(
        "Выберите дату начала мероприятия:",
        reply_markup=get_calendar(prefix="event_")
    )

# Запрашивает выбор даты окончания
@admin_event_router.message(StateFilter(EventForm.waiting_for_end_date))
async def process_end_date_selection(message: Message, state: FSMContext):
    await message.answer(
        "Выберите дату окончания мероприятия:",
        reply_markup=get_calendar(prefix="event_")
    )

# Обрабатывает выбор даты из календаря
@admin_event_router.callback_query(F.data.startswith("event_select_date:"))
async def process_date_callback(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.debug(f"Processing date callback, state={current_state}, callback_data={callback.data}, user_id={callback.from_user.id}")

    date_str = callback.data[len("event_select_date:"):]  # Извлекаем дату без префикса
    try:
        selected_date = datetime.strptime(date_str, "%d.%m.%Y").replace(tzinfo=MOSCOW_TZ)
        current_time = datetime.now(MOSCOW_TZ)
        if selected_date.date() < current_time.date():
            await callback.message.edit_text(
                "Дата не может быть в прошлом. Выберите другую дату:",
                reply_markup=get_calendar(prefix="event_")
            )
            await callback.answer()
            return

        current_state = await state.get_state()
        if current_state == EventForm.waiting_for_start_date.state:
            await state.update_data(start_date=selected_date)
            await state.set_state(EventForm.waiting_for_start_time)
            await callback.message.edit_text(
                f"Выбрана дата начала: {date_str}. Выберите время начала:",
                reply_markup=get_time_keyboard(prefix="event_")
            )
        elif current_state == EventForm.waiting_for_end_date.state:
            data = await state.get_data()
            start_date = data.get("start_date")
            if selected_date.date() < start_date.date():
                logger.warning(f"End date {date_str} before start date")
                await callback.message.edit_text(
                    "Дата окончания не может быть раньше даты начала. Выберите другую дату:",
                    reply_markup=get_calendar(prefix="event_")
                )
                await callback.answer()
                return
            await state.update_data(end_date=selected_date)
            await state.set_state(EventForm.waiting_for_end_time)
            await callback.message.edit_text(
                f"Выбрана дата окончания: {date_str}. Выберите время окончания:",
                reply_markup=get_time_keyboard(prefix="event_")
            )
        elif current_state == EditEventForm.waiting_for_start_date.state:
            if selected_date.date() < current_time.date():
                await callback.message.edit_text(
                    "Дата начала не может быть в прошлом. Выберите другую дату:",
                    reply_markup=get_calendar(prefix="event_")
                )
                await callback.answer()
                return
            await state.update_data(start_date=selected_date)
            await state.set_state(EditEventForm.waiting_for_start_time)
            await callback.message.edit_text(
                f"Выбрана дата начала: {date_str}. Выберите время начала:",
                reply_markup=get_time_keyboard(prefix="event_")
            )
        elif current_state == EditEventForm.waiting_for_end_date.state:
            data = await state.get_data()
            event = data.get("event")
            start_date = datetime.fromisoformat(event["start_date"].replace("Z", "+03:00")).date()
            if selected_date.date() < start_date:
                logger.warning(f"End date {date_str} before start date")
                await callback.message.edit_text(
                    "Дата окончания не может быть раньше даты начала. Выберите другую дату:",
                    reply_markup=get_calendar(prefix="event_")
                )
                await callback.answer()
                return
            await state.update_data(end_date=selected_date)
            await state.set_state(EditEventForm.waiting_for_end_time)
            await callback.message.edit_text(
                f"Выбрана дата окончания: {date_str}. Выберите время окончания:",
                reply_markup=get_time_keyboard(prefix="event_")
            )
    except ValueError as e:
        logger.error(f"Invalid date format: {date_str}, error: {e}")
        await callback.message.edit_text(
            "Ошибка в формате даты. Попробуйте снова:",
            reply_markup=get_calendar(prefix="event_")
        )
    except Exception as e:
        logger.error(f"Unexpected error in date callback: {e}")
        await callback.message.edit_text(
            "Произошла ошибка при выборе даты. Попробуйте снова:",
            reply_markup=get_calendar(prefix="event_")
        )
    await callback.answer()

# Обрабатывает навигацию по месяцам в календаре
@admin_event_router.callback_query(F.data.startswith(("event_prev_month:", "event_next_month:")))
async def process_month_navigation(callback: CallbackQuery, state: FSMContext):
    try:
        _, month, year = callback.data.split(":")
        month, year = int(month), int(year)
        calendar_markup = get_calendar(year, month, prefix="event_")
        if not calendar_markup:
            logger.error(f"Failed to generate calendar for month {month}, year {year}")
            await callback.message.edit_text(
                "Ошибка при загрузке календаря. Попробуйте снова:",
                reply_markup=get_calendar(prefix="event_")
            )
        else:
            await callback.message.edit_reply_markup(reply_markup=calendar_markup)
    except ValueError as e:
        logger.error(f"Invalid month/year: {month}/{year}, error: {e}")
        await callback.message.edit_text(
            "Ошибка при навигации по календарю. Попробуйте снова:",
            reply_markup=get_calendar(prefix="event_")
        )
    except Exception as e:
        logger.error(f"Unexpected error in month navigation: {e}")
        await callback.message.edit_text(
            "Произошла ошибка при навигации. Попробуйте снова:",
            reply_markup=get_calendar(prefix="event_")
        )
    await callback.answer()

# Обрабатывает запрос на ручной ввод времени
@admin_event_router.callback_query(F.data == "event_manual_time")
async def process_manual_time_request(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state in (EventForm.waiting_for_start_time.state, EditEventForm.waiting_for_start_time.state):
        await callback.message.edit_text(
            "Введите время начала (формат ЧЧ:ММ, например, 15:30):",
        )
    elif current_state in (EventForm.waiting_for_end_time.state, EditEventForm.waiting_for_end_time.state):
        await callback.message.edit_text(
            "Введите время окончания (формат ЧЧ:ММ, например, 15:30):",
        )
    await callback.answer()

# Обрабатывает выбор времени из клавиатуры
@admin_event_router.callback_query(F.data.startswith("event_select_time:"))
async def process_time_callback(callback: CallbackQuery, state: FSMContext):

    current_state = await state.get_state()
    logger.debug(f"Processing time callback, state={current_state}, callback_data={callback.data}, user_id={callback.from_user.id}")

    time_str = callback.data[len("event_select_time:"):]  # Извлекаем время без префикса
    try:
        if len(time_str) == 1 or (len(time_str) == 2 and time_str.isdigit()):
            time_str = f"{time_str.zfill(2)}:00"
        datetime.strptime(time_str, "%H:%M")
        current_state = await state.get_state()
        data = await state.get_data()

        if current_state == EventForm.waiting_for_start_time.state:
            start_date = data.get("start_date")
            start_datetime = datetime.strptime(f"{start_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            if start_datetime < datetime.now(MOSCOW_TZ):
                logger.warning(f"Selected past start time: {time_str}")
                await callback.message.edit_text(
                    "Время начала не может быть в прошлом. Выберите другое время:",
                    reply_markup=get_time_keyboard(prefix="event_")
                )
                await callback.answer()
                return
            await state.update_data(start_datetime=start_datetime)
            await state.set_state(EventForm.waiting_for_end_date)
            await callback.message.edit_text(
                f"Время начала ({time_str}) сохранено. Выберите дату окончания:",
                reply_markup=get_calendar(prefix="event_")
            )
        elif current_state == EventForm.waiting_for_end_time.state:
            end_date = data.get("end_date")
            end_datetime = datetime.strptime(f"{end_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            start_datetime = data.get("start_datetime")
            if end_datetime <= start_datetime:
                logger.warning(f"End time {time_str} not after start time")
                await callback.message.edit_text(
                    "Время окончания должно быть позже времени начала. Выберите другое время:",
                    reply_markup=get_time_keyboard(prefix="event_")
                )
                await callback.answer()
                return
            await state.update_data(end_datetime=end_datetime)
            await state.set_state(EventForm.waiting_for_location)
            await callback.message.edit_text(
                f"Время окончания ({time_str}) сохранено. Введите место проведения мероприятия:",
            )
        elif current_state == EditEventForm.waiting_for_start_time.state:
            start_date = data.get("start_date")
            start_datetime = datetime.strptime(f"{start_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            if start_datetime < datetime.now(MOSCOW_TZ):
                logger.warning(f"Selected past start time: {time_str}")
                await callback.message.edit_text(
                    "Время начала не может быть в прошлом. Выберите другое время:",
                    reply_markup=get_time_keyboard(prefix="event_")
                )
                await callback.answer()
                return
            event = data.get("event")
            updated_event = await update_event(
                event_id=event["id"],
                updated_fields={"start_date": start_datetime.isoformat()},
                bot=None
            )
            if updated_event:
                logger.info(f"Event {event['id']} start_date updated to {start_datetime.isoformat()}")
                event["start_date"] = updated_event.get("start_date", start_datetime.isoformat())
                end_datetime = datetime.fromisoformat(event["end_date"].replace("Z", "+03:00"))
                if end_datetime <= start_datetime:
                    logger.warning(f"End date {end_datetime} not after new start date {start_datetime}")
                    await callback.message.edit_text(
                        "Дата окончания должна быть позже новой даты начала. Обновите дату окончания:",
                        reply_markup=get_calendar(prefix="event_")
                    )
                    await state.set_state(EditEventForm.waiting_for_end_date)
                    await state.update_data(start_datetime=start_datetime, end_date=end_datetime)
                    await callback.answer()
                    return
                await state.update_data(event=updated_event)
                await callback.message.delete()
                await callback.message.answer(
                    f"Дата и время начала обновлены: {start_datetime.strftime('%d.%m.%Y %H:%M')}.",
                    reply_markup=edit_event_keyboard()
                )
                await state.set_state(EditEventForm.choosing_field)
            else:
                logger.error(f"Failed to update start time for event {event['id']}")
                await callback.message.edit_text(
                    "Ошибка при обновлении времени начала. Попробуйте снова:",
                    reply_markup=get_time_keyboard(prefix="event_")
                )
        elif current_state == EditEventForm.waiting_for_end_time.state:
            end_date = data.get("end_date")
            end_datetime = datetime.strptime(f"{end_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
            event = data.get("event")
            start_datetime = datetime.fromisoformat(event["start_date"].replace("Z", "+03:00"))
            if end_datetime <= start_datetime:
                logger.warning(f"End time {time_str} not after start time")
                await callback.message.edit_text(
                    "Время окончания должно быть позже времени начала. Выберите другое время:",
                    reply_markup=get_time_keyboard(prefix="event_")
                )
                await callback.answer()
                return
            updated_event = await update_event(
                event_id=event["id"],
                updated_fields={"end_date": end_datetime.isoformat()},
                bot=None
            )
            if updated_event:
                logger.info(f"Event {event['id']} end_date updated to {end_datetime.isoformat()}")
                event["end_date"] = updated_event.get("end_date", end_datetime.isoformat())
                await state.update_data(event=updated_event)
                await callback.message.delete()
                await callback.message.answer(
                    f"Дата и время окончания обновлены: {end_datetime.strftime('%d.%m.%Y %H:%M')}.",
                    reply_markup=edit_event_keyboard()
                )
                await state.set_state(EditEventForm.choosing_field)
            else:
                logger.error(f"Failed to update end time for event {event['id']}")
                await callback.message.edit_text(
                    "Ошибка при обновлении времени окончания. Попробуйте снова:",
                    reply_markup=get_time_keyboard(prefix="event_")
                )
    except ValueError as e:
        logger.error(f"Invalid time format: {time_str}, error: {e}")
        await callback.message.edit_text(
            f"Неверный формат времени: '{time_str}'. Выберите время в формате ЧЧ:ММ (например, 22:00):",
            reply_markup=get_time_keyboard(prefix="event_")
        )
    except (ValidationError, TelegramBadRequest) as e:
        logger.error(f"Error processing time callback: {e}")
        await callback.message.edit_text(
            f"Ошибка при обработке времени '{time_str}'. Выберите время в формате ЧЧ:ММ (например, 22:00):",
            reply_markup=get_time_keyboard(prefix="event_")
        )
    except Exception as e:
        logger.error(f"Unexpected error in time callback: {e}")
        await callback.message.edit_text(
            "Произошла ошибка при выборе времени. Попробуйте снова:",
            reply_markup=get_time_keyboard(prefix="event_")
        )
    await callback.answer()

# Обработчики ручного ввода времени для создания мероприятия
@admin_event_router.message(EventForm.waiting_for_start_time)
async def process_manual_start_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    match = TIME_PATTERN.match(time_str)
    if not match:
        logger.warning(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="event_")
        )
        return

    try:
        hours, minutes = map(int, match.groups())
        if hours > 23 or minutes > 59:
            logger.warning(f"User {message.from_user.id} provided out-of-range time: {time_str}")
            await message.answer(
                "Часы должны быть от 0 до 23, минуты от 00 до 59. Введите корректное время:",
                reply_markup=get_time_keyboard(prefix="event_")
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
                reply_markup=get_time_keyboard(prefix="event_")
            )
            return
        
        await state.update_data(start_datetime=start_datetime)
        await state.set_state(EventForm.waiting_for_end_date)
        await message.answer(
            f"Время начала ({time_str}) сохранено. Выберите дату окончания:",
            reply_markup=get_calendar(prefix="event_")
        )
    except ValueError:
        logger.error(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="event_")
        )

@admin_event_router.message(EventForm.waiting_for_end_time)
async def process_manual_end_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    match = TIME_PATTERN.match(time_str)
    if not match:
        logger.warning(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="event_")
        )
        return

    try:
        hours, minutes = map(int, match.groups())
        if hours > 23 or minutes > 59:
            logger.warning(f"User {message.from_user.id} provided out-of-range time: {time_str}")
            await message.answer(
                "Часы должны быть от 0 до 23, минуты от 00 до 59. Введите корректное время:",
                reply_markup=get_time_keyboard(prefix="event_")
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
                reply_markup=get_time_keyboard(prefix="event_")
            )
            return
        
        await state.update_data(end_datetime=end_datetime)
        await state.set_state(EventForm.waiting_for_location)
        await message.answer(
            f"Время окончания ({time_str}) сохранено. Введите место проведения мероприятия:"
        )
    except ValueError:
        logger.error(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="event_")
        )

# Обработчики ручного ввода времени для редактирования мероприятия
@admin_event_router.message(EditEventForm.waiting_for_start_time)
async def process_manual_edit_start_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    match = TIME_PATTERN.match(time_str)
    if not match:
        logger.warning(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="event_")
        )
        return

    try:
        hours, minutes = map(int, match.groups())
        if hours > 23 or minutes > 59:
            logger.warning(f"User {message.from_user.id} provided out-of-range time: {time_str}")
            await message.answer(
                "Часы должны быть от 0 до 23, минуты от 00 до 59. Введите корректное время:",
                reply_markup=get_time_keyboard(prefix="event_")
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
                reply_markup=get_time_keyboard(prefix="event_")
            )
            return
        
        event = data.get("event")
        updated_event = await update_event(
            event_id=event["id"],
            updated_fields={"start_date": start_datetime.isoformat()},
            bot=None
        )
        if updated_event:
            end_datetime = datetime.fromisoformat(event["end_date"].replace("Z", "+03:00"))
            if end_datetime <= start_datetime:
                logger.warning(f"User {message.from_user.id} set end date {end_datetime} not after new start date {start_datetime}")
                await message.answer(
                    "Дата окончания должна быть позже новой даты начала. Пожалуйста, обновите дату окончания:",
                    reply_markup=get_calendar(prefix="event_")
                )
                await state.set_state(EditEventForm.waiting_for_end_date)
                await state.update_data(start_datetime=start_datetime, end_date=end_datetime)
                return
            
            await state.update_data(event=updated_event)
            text = (
                f"Название: {updated_event['title']}\n"
                f"Описание: {updated_event['description']}\n"
                f"Информация: {updated_event['info']}\n"
                f"Дата начала: {format_datetime(updated_event.get('start_date'))}\n"
                f"Дата окончания: {format_datetime(updated_event.get('end_date'))}\n"
                f"Место: {updated_event['location']}\n"
                f"Ссылка для регистрации: {updated_event.get('url')}"
            )
            photo_url = updated_event.get("photo")
            if photo_url:
                try:
                    await message.answer_photo(
                        photo=photo_url,
                        caption=text,
                        parse_mode="Markdown",
                        reply_markup=edit_event_keyboard()
                    )
                except Exception as e:
                    logger.error(f"Failed to send photo for event {event['id']}: {e}")
                    await message.answer(
                        text + "\n\n(Фото недоступно)",
                        parse_mode="Markdown",
                        reply_markup=edit_event_keyboard()
                    )
            else:
                await message.answer(
                    text + "\n\n(Фото отсутствует)",
                    parse_mode="Markdown",
                    reply_markup=edit_event_keyboard()
                )
            await state.set_state(EditEventForm.choosing_field)
        else:
            logger.error(f"Failed to update start time for event {event['id']}")
            await message.answer(
                "Ошибка при обновлении времени начала. Попробуйте снова:",
                reply_markup=get_time_keyboard(prefix="event_")
            )
    except ValueError:
        logger.error(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="event_")
        )

@admin_event_router.message(EditEventForm.waiting_for_end_time)
async def process_manual_edit_end_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    match = TIME_PATTERN.match(time_str)
    if not match:
        logger.warning(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="event_")
        )
        return

    try:
        hours, minutes = map(int, match.groups())
        if hours > 23 or minutes > 59:
            logger.warning(f"User {message.from_user.id} provided out-of-range time: {time_str}")
            await message.answer(
                "Часы должны быть от 0 до 23, минуты от 00 до 59. Введите корректное время:",
                reply_markup=get_time_keyboard(prefix="event_")
            )
            return
        time_str = f"{hours:02d}:{minutes:02d}"
        data = await state.get_data()
        end_date = data.get("end_date")
        end_datetime = datetime.strptime(f"{end_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=MOSCOW_TZ)
        event = data.get("event")
        start_datetime = datetime.fromisoformat(event["start_date"].replace("Z", "+03:00"))
        
        if end_datetime <= start_datetime:
            logger.warning(f"User {message.from_user.id} selected end time {time_str} not after start time")
            await message.answer(
                "Время окончания должно быть позже времени начала. Введите другое время:",
                reply_markup=get_time_keyboard(prefix="event_")
            )
            return
        
        updated_event = await update_event(
            event_id=event["id"],
            updated_fields={"end_date": end_datetime.isoformat()},
            bot=None
        )
        if updated_event:
            await state.update_data(event=updated_event)
            text = (
                f"Название: {updated_event['title']}\n"
                f"Описание: {updated_event['description']}\n"
                f"Информация: {updated_event['info']}\n"
                f"Дата начала: {format_datetime(updated_event.get('start_date'))}\n"
                f"Дата окончания: {format_datetime(updated_event.get('end_date'))}\n"
                f"Место: {updated_event['location']}\n"
                f"Ссылка для регистрации: {updated_event.get('url')}"
            )
            photo_url = updated_event.get("photo")
            if photo_url:
                try:
                    await message.answer_photo(
                        photo=photo_url,
                        caption=text,
                        parse_mode="Markdown",
                        reply_markup=edit_event_keyboard()
                    )
                except Exception as e:
                    logger.error(f"Failed to send photo for event {event['id']}: {e}")
                    await message.answer(
                        text + "\n\n(Фото недоступно)",
                        parse_mode="Markdown",
                        reply_markup=edit_event_keyboard()
                    )
            else:
                await message.answer(
                    text + "\n\n(Фото отсутствует)",
                    parse_mode="Markdown",
                    reply_markup=edit_event_keyboard()
                )
            await state.set_state(EditEventForm.choosing_field)
        else:
            logger.error(f"Failed to update end time for event {event['id']}")
            await message.answer(
                "Ошибка при обновлении времени окончания. Попробуйте снова:",
                reply_markup=get_time_keyboard(prefix="event_")
            )
    except ValueError:
        logger.error(f"User {message.from_user.id} provided invalid time format: {time_str}")
        await message.answer(
            f"Неверный формат времени: '{time_str}'. Введите время в формате ЧЧ:ММ (например, 15:30):",
            reply_markup=get_time_keyboard(prefix="event_")
        )

# =================================================================================================
# Обработчики редактирования и удаления мероприятий
# =================================================================================================

# Начинает процесс редактирования мероприятия
@admin_event_router.message(F.text == "Редактировать мероприятие")
async def edit_event_start(message: Message):
    events = await fetch_events()
    if not events:
        await message.answer("Нет доступных мероприятий для редактирования")
        return
    builder = ReplyKeyboardBuilder()
    for event in events:
        title = event.get("title")
        builder.button(text=f"✏️ {title}")
    builder.button(text="Назад")
    builder.adjust(1)
    await message.answer(
        "Выберите мероприятие для редактирования:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Обрабатывает выбор мероприятия для редактирования
@admin_event_router.message(F.text.startswith("✏️ "))
async def edit_event_select(message: Message, state: FSMContext):
    event_title = message.text[2:].strip()
    event = await get_event_by_title(event_title)
    if not event:
        await message.answer("Не удалось найти мероприятие.")
        return
    await state.clear()
    await state.set_state(EditEventForm.choosing_field)
    await state.update_data(event=event)
    current_event_text = (
        f"Название: {event['title']}\n"
        f"Описание: {event['description']}\n"
        f"Информация: {event['info']}\n"
        f"Дата начала: {format_datetime(event.get('start_date'))}\n"
        f"Дата окончания: {format_datetime(event.get('end_date'))}\n"
        f"Место: {event['location']}\n"
        f"Ссылка для регистрации: {event.get('url')}"
    )
    photo_url = event.get("photo")
    if photo_url:
        try:
            await message.answer_photo(
                photo=photo_url,
                caption=current_event_text,
                parse_mode="Markdown",
                reply_markup=edit_event_keyboard()
            )
        except Exception as e:
            logger.error(f"Failed to send photo for event {event['id']}: {e}")
            await message.answer(
                current_event_text + "\n\n(Фото недоступно)",
                reply_markup=edit_event_keyboard()
            )
    else:
        await message.answer(
            current_event_text + "\n\n(Фото отсутствует)",
            reply_markup=edit_event_keyboard()
        )

# Запрашивает новое название для редактирования
@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить название")
async def edit_event_title(message: Message, state: FSMContext):
    await message.answer("Введите новое название:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_title)

# Запрашивает новое фото для редактирования
@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить фото")
async def edit_event_photo(message: Message, state: FSMContext):
    await message.answer("Отправьте новое фото:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_photo)

# Запрашивает новое описание для редактирования
@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить описание")
async def edit_event_description(message: Message, state: FSMContext):
    await message.answer("Введите новое описание:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_description)

# Запрашивает новую информацию для редактирования
@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить информацию")
async def edit_event_info(message: Message, state: FSMContext):
    await message.answer("Введите новую информацию:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_info)

# Запрашивает новую дату начала для редактирования
@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить дату начала")
async def edit_event_start_date(message: Message, state: FSMContext):
    await message.answer("Выберите новую дату начала:", reply_markup=get_calendar(prefix="event_"))
    await state.set_state(EditEventForm.waiting_for_start_date)

# Запрашивает новую дату окончания для редактирования
@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить дату окончания")
async def edit_event_end_date(message: Message, state: FSMContext):
    await message.answer("Выберите новую дату окончания:", reply_markup=get_calendar(prefix="event_"))
    await state.set_state(EditEventForm.waiting_for_end_date)

# Запрашивает новую локацию для редактирования
@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить локацию")
async def edit_event_location(message: Message, state: FSMContext):
    await message.answer("Введите новую локацию:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_location)

# Запрашивает новую ссылку для редактирования
@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить ссылку")
async def edit_event_url(message: Message, state: FSMContext):
    await message.answer("Введите новую ссылку:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_url)

# Обрабатывает новое название мероприятия
@admin_event_router.message(EditEventForm.waiting_for_title)
async def process_event_title(message: Message, state: FSMContext):
    new_title = message.text.strip()
    if not new_title:
        await message.answer("Название не может быть пустым.", reply_markup=cancel_keyboard())
        return
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка доступа к мероприятию.", reply_markup=events_management_keyboard())
        await state.clear()
        return
    updated_event = await update_event(event_id=event["id"], updated_fields={"title": new_title}, bot=None)
    if updated_event:
        logger.info(f"Event {event['id']} title updated to '{new_title}'")
        event["title"] = new_title
        await state.update_data(event=event)
        await message.answer("Название мероприятия обновлено.", reply_markup=edit_event_keyboard())
        await state.set_state(EditEventForm.choosing_field)
    else:
        logger.error(f"Failed to update title for event {event['id']}")
        await message.answer("Ошибка при обновлении названия. Попробуйте снова.", reply_markup=edit_event_keyboard())

# Обрабатывает новое фото мероприятия
@admin_event_router.message(EditEventForm.waiting_for_photo)
async def process_event_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка доступа к мероприятию.", reply_markup=events_management_keyboard())
        await state.clear()
        return
    is_valid, result = await validate_photo(message)
    if not is_valid:
        await message.answer(result, reply_markup=cancel_keyboard())
        return
    photo_file_id = result
    updated_event = await update_event(event_id=event["id"], updated_fields={"photo": photo_file_id}, bot=bot)
    if updated_event and isinstance(updated_event, dict):
        logger.info(f"Photo updated for event {event['id']}")
        event["photo"] = updated_event.get("photo")
        await state.update_data(event=event)
        await message.answer("Фото мероприятия обновлено.", reply_markup=edit_event_keyboard())
        await state.set_state(EditEventForm.choosing_field)
    else:
        logger.error(f"Failed to update photo for event {event['id']}")
        await message.answer("Ошибка при обновлении фото. Попробуйте снова.", reply_markup=cancel_keyboard())

# Обрабатывает новое описание мероприятия
@admin_event_router.message(EditEventForm.waiting_for_description)
async def process_event_description(message: Message, state: FSMContext):
    new_description = message.text.strip()
    if not new_description:
        await message.answer("Описание не может быть пустым.", reply_markup=cancel_keyboard())
        return
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка доступа к мероприятию.", reply_markup=events_management_keyboard())
        await state.clear()
        return
    updated_event = await update_event(event_id=event["id"], updated_fields={"description": new_description}, bot=None)
    if updated_event:
        logger.info(f"Description updated for event {event['id']}")
        event["description"] = new_description
        await state.update_data(event=event)
        await message.answer("Описание мероприятия обновлено.", reply_markup=edit_event_keyboard())
        await state.set_state(EditEventForm.choosing_field)
    else:
        logger.error(f"Failed to update description for event {event['id']}")
        await message.answer("Ошибка при обновлении описания. Попробуйте снова.", reply_markup=edit_event_keyboard())

# Обрабатывает новую информацию о мероприятии
@admin_event_router.message(EditEventForm.waiting_for_info)
async def process_event_info(message: Message, state: FSMContext):
    new_info = message.text.strip()
    if not new_info:
        await message.answer("Информация не может быть пустой.", reply_markup=cancel_keyboard())
        return
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка доступа к мероприятию.", reply_markup=events_management_keyboard())
        await state.clear()
        return
    updated_event = await update_event(event_id=event["id"], updated_fields={"info": new_info}, bot=None)
    if updated_event:
        logger.info(f"Info updated for event {event['id']}")
        event["info"] = new_info
        await state.update_data(event=event)
        await message.answer("Информация о мероприятии обновлена.", reply_markup=edit_event_keyboard())
        await state.set_state(EditEventForm.choosing_field)
    else:
        logger.error(f"Failed to update info for event {event['id']}")
        await message.answer("Ошибка при обновлении информации. Попробуйте снова.", reply_markup=edit_event_keyboard())

# Обрабатывает новую локацию мероприятия
@admin_event_router.message(EditEventForm.waiting_for_location)
async def process_event_location(message: Message, state: FSMContext):
    new_location = message.text.strip()
    if not new_location:
        await message.answer("Локация не может быть пустой.", reply_markup=cancel_keyboard())
        return
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка доступа к мероприятию.", reply_markup=events_management_keyboard())
        await state.clear()
        return
    updated_event = await update_event(event_id=event["id"], updated_fields={"location": new_location}, bot=None)
    if updated_event:
        logger.info(f"Location updated for event {event['id']}")
        event["location"] = new_location
        await state.update_data(event=event)
        await message.answer("Локация обновлена.", reply_markup=edit_event_keyboard())
        await state.set_state(EditEventForm.choosing_field)
    else:
        logger.error(f"Failed to update location for event {event['id']}")
        await message.answer("Ошибка при обновлении локации. Попробуйте снова.", reply_markup=edit_event_keyboard())

# Обрабатывает новую ссылку мероприятия
@admin_event_router.message(EditEventForm.waiting_for_url)
async def process_event_url(message: Message, state: FSMContext):
    new_url = message.text.strip()
    if not new_url:
        await message.answer("Ссылка не может быть пустой.", reply_markup=cancel_keyboard())
        return
    if not URL_PATTERN.match(new_url):
        logger.warning(f"Invalid URL: {new_url}")
        await message.answer("Неверный формат ссылки. Введите корректную ссылку:", reply_markup=cancel_keyboard())
        return
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка доступа к мероприятию.", reply_markup=events_management_keyboard())
        await state.clear()
        return
    updated_event = await update_event(event_id=event["id"], updated_fields={"url": new_url}, bot=None)
    if updated_event:
        logger.info(f"URL updated for event {event['id']}")
        event["url"] = new_url
        await state.update_data(event=event)
        await message.answer("Ссылка обновлена.", reply_markup=edit_event_keyboard())
        await state.set_state(EditEventForm.choosing_field)
    else:
        logger.error(f"Failed to update URL for event {event['id']}")
        await message.answer("Ошибка при обновлении ссылки. Попробуйте снова.", reply_markup=edit_event_keyboard())

# Начинает процесс удаления мероприятия
@admin_event_router.message(F.text == "Удалить мероприятие")
async def delete_event_start(message: Message):
    events = await fetch_events()
    if not events:
        await message.answer("Нет доступных мероприятий для удаления")
        return
    builder = ReplyKeyboardBuilder()
    for event in events:
        title = event.get("title")
        builder.button(text=f"❌ {title}")
    builder.button(text="Назад")
    builder.adjust(1)
    await message.answer(
        "Выберите мероприятие для удаления:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

# Обрабатывает выбор мероприятия для удаления
@admin_event_router.message(F.text.startswith("❌ "))
async def delete_event_select(message: Message, state: FSMContext):
    event_title = message.text[2:].strip()
    event = await get_event_by_title(event_title)
    if not event:
        await message.answer("Не удалось найти мероприятие.")
        return
    await state.update_data(event=event)
    await state.set_state(DeleteEventForm.waiting_for_confirmation)
    current_event_text = (
        f"Название: {event['title']}\n"
        f"Описание: {event['description']}\n"
        f"Информация: {event['info']}\n"
        f"Дата начала: {format_datetime(event.get('start_date'))}\n"
        f"Дата окончания: {format_datetime(event.get('end_date'))}\n"
        f"Место: {event['location']}"
    )
    builder = ReplyKeyboardBuilder()
    builder.button(text="Удалить")
    builder.button(text="Отмена")
    builder.adjust(1)
    photo_url = event.get("photo")
    if photo_url:
        try:
            await message.answer_photo(
                photo=photo_url,
                caption=f"Вы выбрали мероприятие:\n\n{current_event_text}\n\nВы действительно хотите удалить это мероприятие?",
                parse_mode="Markdown",
                reply_markup=builder.as_markup(resize_keyboard=True)
            )
        except Exception as e:
            logger.error(f"Failed to send photo for event {event['id']}: {e}")
            await message.answer(
                f"Вы выбрали мероприятие:\n\n{current_event_text}\n\n(Фото недоступно)\n\nВы действительно хотите удалить это мероприятие?",
                reply_markup=builder.as_markup(resize_keyboard=True)
            )
    else:
        await message.answer(
            f"Вы выбрали мероприятие:\n\n{current_event_text}\n\n(Фото отсутствует)\n\nВы действительно хотите удалить это мероприятие?",
            reply_markup=builder.as_markup(resize_keyboard=True)
        )

# Подтверждает удаление мероприятия
@admin_event_router.message(F.text == "Удалить", StateFilter(DeleteEventForm.waiting_for_confirmation))
async def confirm_delete_event(message: Message, state: FSMContext):
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка: мероприятие не найдено.")
        return
    success = await delete_event(event_id=event["id"])
    if success:
        logger.info(f"Event {event['id']} deleted")
        await message.answer("Мероприятие успешно удалено.", reply_markup=events_management_keyboard())
    else:
        logger.error(f"Failed to delete event {event['id']}")
        await message.answer("Не удалось удалить мероприятие. Попробуйте снова.", reply_markup=events_management_keyboard())
    await state.clear()