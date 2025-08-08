import aiohttp
import logging
from datetime import datetime
from pydantic import ValidationError
from aiogram.exceptions import TelegramBadRequest
from aiogram import Bot, F, Router
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from data.config import config_settings
from admin.keyboards.admin_reply import events_management_keyboard, admin_keyboard, cancel_keyboard, edit_event_keyboard
from data.url import url_event
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID
from utils.photo import download_photo_from_telegram, validate_photo
from utils.calendar import get_calendar, get_time_keyboard, format_datetime
from utils.constants import URL_PATTERN, MOSCOW_TZ, TIME_PATTERN
from utils.check_length import check_length

logger = logging.getLogger(__name__)

admin_event_router = Router()
admin_event_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([ADMIN_CHAT_ID], show_message=False)
)

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
    waiting_for_enable_registration = State()
    waiting_for_registration_url = State()
    waiting_for_enable_tickets = State()
    waiting_for_ticket_url = State()

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
    waiting_for_enable_registration = State()
    waiting_for_registration_url = State()
    waiting_for_enable_tickets = State()
    waiting_for_ticket_url = State()

class DeleteEventForm(StatesGroup):
    waiting_for_confirmation = State()

# =================================================================================================
# Функции для работы с API
# =================================================================================================

async def create_new_event(event_data: dict, photo_file_id: str, bot: Bot) -> dict:
    url = f"{url_event}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    form_data = aiohttp.FormData()
    
    for key, value in event_data.items():
        if value is not None:
            if isinstance(value, bool):
                form_data.add_field(key, str(value).lower())
            else:
                form_data.add_field(key, str(value))
    
    try:
        if photo_file_id:
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
            logger.debug(f"Sending request to create event: {event_data}")
            async with session.post(url, headers=headers, data=form_data) as response:
                response_text = await response.text()
                if response.status == 201:
                    logger.info(f"Event created successfully: {event_data['title']}")
                    return await response.json()
                logger.error(f"Failed to create event, status={response.status}, body={response_text}")
                return None
    except aiohttp.ClientError as e:
        logger.error(f"Network error creating event: {e}")
        return None

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
        elif value is not None:
            if isinstance(value, bool):
                form_data.add_field(key, str(value).lower())
            else:
                form_data.add_field(key, str(value))
    
    try:
        async with aiohttp.ClientSession() as session:
            logger.debug(f"Sending request to update event {event_id}: {updated_fields}")
            async with session.patch(url, headers=headers, data=form_data) as response:
                response_text = await response.text()
                if response.status == 200:
                    logger.info(f"Event {event_id} updated successfully")
                    return await response.json()
                logger.error(f"Failed to update event {event_id}, status={response.status}, body={response_text}")
                return None
    except Exception as e:
        logger.error(f"Error updating event {event_id}: {e}")
        return None

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

async def get_event_by_title(title: str) -> dict:
    events = await fetch_events()
    for event in events:
        if event.get("title") == title:
            return event
    logger.warning(f"Event with title '{title}' not found")
    return None

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
# Обработчики меню
# =================================================================================================

@admin_event_router.message(F.text == "🎉 Мероприятия")
async def handle_events(message: Message):
    await message.answer(
        "Управление мероприятиями:",
        reply_markup=events_management_keyboard()
    )

@admin_event_router.message(F.text == "Назад")
async def back_to_admin_menu(message: Message):
    await message.answer(
        "Вы вернулись в главное меню администратора.",
        reply_markup=admin_keyboard()
    )

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

@admin_event_router.message(F.text == "Добавить мероприятие")
async def handle_add_event(message: Message, state: FSMContext):
    await state.set_state(EventForm.waiting_for_title)
    await message.answer(
        "Введите название мероприятия:",
        reply_markup=cancel_keyboard()
    )

@admin_event_router.message(StateFilter(EventForm.waiting_for_title))
async def process_event_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым. Введите название:", reply_markup=cancel_keyboard())
        return
    if check_length(title, max_length=100):
        await message.answer("Название слишком длинное. Максимальная длина - 100 символов.", reply_markup=cancel_keyboard())
        return
    await state.update_data(title=title)
    await state.set_state(EventForm.waiting_for_photo)
    await message.answer("Отправьте фото для мероприятия:", reply_markup=cancel_keyboard())

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

@admin_event_router.message(StateFilter(EventForm.waiting_for_description))
async def process_event_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if not description:
        await message.answer("Описание не может быть пустым. Введите описание:", reply_markup=cancel_keyboard())
        return
    if check_length(description, max_length=100):
        await message.answer("Описание слишком длинное. Максимальная длина - 500 символов.", reply_markup=cancel_keyboard())
        return
    await state.update_data(description=description)
    await state.set_state(EventForm.waiting_for_info)
    await message.answer("Введите дополнительную информацию о мероприятии:", reply_markup=cancel_keyboard())

@admin_event_router.message(StateFilter(EventForm.waiting_for_info))
async def process_event_info(message: Message, state: FSMContext):
    info = message.text.strip()
    if not info:
        await message.answer("Информация не может быть пустой. Введите информацию:", reply_markup=cancel_keyboard())
        return
    if check_length(info, max_length=400):
        await message.answer("Информация слишком длинная. Максимальная длина - 400 символов.", reply_markup=cancel_keyboard())
        return
    await state.update_data(info=info)
    await state.set_state(EventForm.waiting_for_start_date)
    await message.answer("Выберите дату начала мероприятия:", reply_markup=get_calendar(prefix="event_"))

@admin_event_router.message(StateFilter(EventForm.waiting_for_location))
async def process_event_location(message: Message, state: FSMContext):
    location = message.text.strip()
    if not location:
        await message.answer("Место проведения не может быть пустым. Введите место:", reply_markup=cancel_keyboard())
        return
    if check_length(location, max_length=100):
        await message.answer("Место проведения слишком длинное. Максимальная длина - 100 символов.", reply_markup=cancel_keyboard())
        return
    await state.update_data(location=location)
    await state.set_state(EventForm.waiting_for_enable_registration)
    builder = ReplyKeyboardBuilder()
    builder.button(text="Да")
    builder.button(text="Нет")
    builder.button(text="Отмена")
    builder.adjust(1)
    await message.answer("Доступна ли регистрация на мероприятие?", reply_markup=builder.as_markup(resize_keyboard=True))

@admin_event_router.message(StateFilter(EventForm.waiting_for_enable_registration))
async def process_enable_registration(message: Message, state: FSMContext):
    choice = message.text.strip().lower()
    logger.debug(f"User {message.from_user.id} sent choice '{choice}' for enable_registration")
    if choice not in ["да", "нет"]:
        logger.warning(f"Invalid choice for enable_registration: '{choice}' by user {message.from_user.id}")
        await message.answer(
            "Пожалуйста, выберите 'Да' или 'Нет':",
            reply_markup=ReplyKeyboardBuilder().add(
                {"text": "Да"}, {"text": "Нет"}, {"text": "Отмена"}
            ).adjust(1).as_markup(resize_keyboard=True)
        )
        return
    enable_registration = choice == "да"
    await state.update_data(enable_registration=enable_registration)
    if enable_registration:
        await state.set_state(EventForm.waiting_for_registration_url)
        await message.answer("Введите ссылку для регистрации:", reply_markup=cancel_keyboard())
    else:
        await state.update_data(registration_url=None)
        await state.set_state(EventForm.waiting_for_enable_tickets)
        builder = ReplyKeyboardBuilder()
        builder.button(text="Да")
        builder.button(text="Нет")
        builder.button(text="Отмена")
        builder.adjust(1)
        await message.answer("Доступна ли покупка билетов на мероприятие?", reply_markup=builder.as_markup(resize_keyboard=True))

@admin_event_router.message(StateFilter(EventForm.waiting_for_registration_url))
async def process_registration_url(message: Message, state: FSMContext):
    url = message.text.strip()
    logger.debug(f"User {message.from_user.id} sent registration_url '{url}'")
    if check_length(url, max_length=70):
        await message.answer("Ссылка слишком длинная. Максимальная длина - 70 символов.", reply_markup=cancel_keyboard())
        return
    if not URL_PATTERN.match(url):
        logger.warning(f"Invalid URL: '{url}' by user {message.from_user.id}")
        await message.answer("Неверный формат ссылки. Введите корректную ссылку:", reply_markup=cancel_keyboard())
        return
    await state.update_data(registration_url=url)
    await state.set_state(EventForm.waiting_for_enable_tickets)
    builder = ReplyKeyboardBuilder()
    builder.button(text="Да")
    builder.button(text="Нет")
    builder.button(text="Отмена")
    builder.adjust(1)
    await message.answer("Доступна ли покупка билетов на мероприятие?", reply_markup=builder.as_markup(resize_keyboard=True))

@admin_event_router.message(StateFilter(EventForm.waiting_for_enable_tickets))
async def process_enable_tickets(message: Message, state: FSMContext):
    choice = message.text.strip().lower()
    logger.debug(f"User {message.from_user.id} sent choice '{choice}' for enable_tickets")
    if choice not in ["да", "нет"]:
        logger.warning(f"Invalid choice for enable_tickets: '{choice}' by user {message.from_user.id}")
        await message.answer(
            "Пожалуйста, выберите 'Да' или 'Нет':",
            reply_markup=ReplyKeyboardBuilder().add(
                {"text": "Да"}, {"text": "Нет"}, {"text": "Отмена"}
            ).adjust(1).as_markup(resize_keyboard=True)
        )
        return
    enable_tickets = choice == "да"
    await state.update_data(enable_tickets=enable_tickets)
    if enable_tickets:
        await state.set_state(EventForm.waiting_for_ticket_url)
        await message.answer("Введите ссылку для покупки билета:", reply_markup=cancel_keyboard())
    else:
        await state.update_data(ticket_url=None)
        await process_create_event(message, state, bot=message.bot)

@admin_event_router.message(StateFilter(EventForm.waiting_for_ticket_url))
async def process_ticket_url_and_create(message: Message, state: FSMContext, bot: Bot):
    url = message.text.strip()
    logger.debug(f"User {message.from_user.id} sent ticket_url '{url}'")
    if check_length(url, max_length=70):
        await message.answer("Ссылка слишком длинная. Максимальная длина - 70 символов.", reply_markup=cancel_keyboard())
        return
    if not URL_PATTERN.match(url):
        logger.warning(f"Invalid URL: '{url}' by user {message.from_user.id}")
        await message.answer("Неверный формат ссылки. Введите корректную ссылку:", reply_markup=cancel_keyboard())
        return
    await state.update_data(ticket_url=url)
    await process_create_event(message, state, bot)

async def process_create_event(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    event_data = {
        "title": data.get("title"),
        "description": data.get("description"),
        "info": data.get("info"),
        "start_date": data.get("start_datetime").isoformat(),
        "end_date": data.get("end_datetime").isoformat(),
        "location": data.get("location"),
        "enable_registration": data.get("enable_registration", False),
        "registration_url": data.get("registration_url"),
        "enable_tickets": data.get("enable_tickets", False),
        "ticket_url": data.get("ticket_url")
    }
    photo_file_id = data.get("photo")
    
    try:
        created_event = await create_new_event(event_data, photo_file_id, bot)
        if created_event:
            caption = (
                f"Мероприятие успешно создано!\n"
                f"{event_data['title']}\n"
                f"{event_data['description']}\n"
                f"{event_data['info']}\n"
                f"{format_datetime(event_data['start_date'])} - {format_datetime(event_data['end_date'])}\n"
                f"{event_data['location']}\n"
                f"Регистрация: {'Включена' if event_data['enable_registration'] else 'Выключена'}\n"
                f"Ссылка на регистрацию: {event_data['registration_url'] or 'Отсутствует'}\n"
                f"Покупка билетов: {'Включена' if event_data['enable_tickets'] else 'Выключена'}\n"
                f"Ссылка на покупку билета: {event_data['ticket_url'] or 'Отсутствует'}"
            )
            photo_url = created_event.get("photo")
            try:
                if photo_url:
                    await message.answer_photo(
                        photo=photo_url,
                        caption=caption,
                        parse_mode="Markdown",
                        reply_markup=events_management_keyboard(),
                    )
                else:
                    await message.answer(caption, reply_markup=events_management_keyboard())
            except TelegramBadRequest as e:
                logger.error(f"Failed to send event message: {e}")
                await message.answer(
                    f"{caption}\n\n(Ошибка отображения фото)",
                    parse_mode="Markdown",
                    reply_markup=events_management_keyboard()
                )
            await state.clear()
            logger.info(f"Event created successfully: {event_data['title']}")
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

@admin_event_router.message(StateFilter(EventForm.waiting_for_start_date))
async def process_start_date_selection(message: Message, state: FSMContext):
    await message.answer(
        "Выберите дату начала мероприятия:",
        reply_markup=get_calendar(prefix="event_")
    )

@admin_event_router.message(StateFilter(EventForm.waiting_for_end_date))
async def process_end_date_selection(message: Message, state: FSMContext):
    await message.answer(
        "Выберите дату окончания мероприятия:",
        reply_markup=get_calendar(prefix="event_")
    )

@admin_event_router.callback_query(F.data.startswith("event_select_date:"))
async def process_date_callback(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.debug(f"Processing date callback, state={current_state}, callback_data={callback.data}, user_id={callback.from_user.id}")
    date_str = callback.data[len("event_select_date:"):]
    
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

@admin_event_router.callback_query(F.data.startswith("event_select_time:"))
async def process_time_callback(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.debug(f"Processing time callback, state={current_state}, callback_data={callback.data}, user_id={callback.from_user.id}")
    time_str = callback.data[len("event_select_time:"):]
    
    try:
        if len(time_str) == 1 or (len(time_str) == 2 and time_str.isdigit()):
            time_str = f"{time_str.zfill(2)}:00"
        datetime.strptime(time_str, "%H:%M")
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
                f"{updated_event['title']}\n"
                f"{updated_event['description']}\n"
                f"{updated_event['info']}\n"
                f"{format_datetime(updated_event.get('start_date'))} - {format_datetime(updated_event.get('end_date'))}\n"
                f"{updated_event['location']}\n"
                f"Регистрация: {'Включена' if updated_event['enable_registration'] else 'Выключена'}\n"
                f"Ссылка на регистрацию: {updated_event.get('registration_url') or 'Отсутствует'}\n"
                f"Покупка билетов: {'Включена' if updated_event['enable_tickets'] else 'Выключена'}\n"
                f"Ссылка на покупку билета: {updated_event.get('ticket_url') or 'Отсутствует'}"
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
                f"{updated_event['title']}\n"
                f"{updated_event['description']}\n"
                f"{updated_event['info']}\n"
                f"{format_datetime(updated_event.get('start_date'))} - {format_datetime(updated_event.get('end_date'))}\n"
                f"{updated_event['location']}\n"
                f"Регистрация: {'Включена' if updated_event['enable_registration'] else 'Выключена'}\n"
                f"Ссылка на регистрацию: {updated_event.get('registration_url') or 'Отсутствует'}\n"
                f"Покупка билетов: {'Включена' if updated_event['enable_tickets'] else 'Выключена'}\n"
                f"Ссылка на покупку билета: {updated_event.get('ticket_url') or 'Отсутствует'}"
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
# Обработчики редактирования мероприятий
# =================================================================================================
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
        f"{event['title']}\n"
        f"{event['description']}\n"
        f"{event['info']}\n"
        f"{format_datetime(event.get('start_date'))} - {format_datetime(event.get('end_date'))}\n"
        f"{event['location']}\n"
        f"Регистрация: {'Включена' if event['enable_registration'] else 'Выключена'}\n"
        f"Ссылка на регистрацию: {event.get('registration_url') or 'Отсутствует'}\n"
        f"Покупка билетов: {'Включена' if event['enable_tickets'] else 'Выключена'}\n"
        f"Ссылка на покупку билета: {event.get('ticket_url') or 'Отсутствует'}"
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

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить название")
async def edit_event_title(message: Message, state: FSMContext):
    await message.answer("Введите новое название:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_title)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить фото")
async def edit_event_photo(message: Message, state: FSMContext):
    await message.answer("Отправьте новое фото:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_photo)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить описание")
async def edit_event_description(message: Message, state: FSMContext):
    await message.answer("Введите новое описание:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_description)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить информацию")
async def edit_event_info(message: Message, state: FSMContext):
    await message.answer("Введите новую информацию:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_info)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить дату начала")
async def edit_event_start_date(message: Message, state: FSMContext):
    await message.answer("Выберите новую дату начала:", reply_markup=get_calendar(prefix="event_"))
    await state.set_state(EditEventForm.waiting_for_start_date)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить дату окончания")
async def edit_event_end_date(message: Message, state: FSMContext):
    await message.answer("Выберите новую дату окончания:", reply_markup=get_calendar(prefix="event_"))
    await state.set_state(EditEventForm.waiting_for_end_date)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить локацию")
async def edit_event_location(message: Message, state: FSMContext):
    await message.answer("Введите новую локацию:", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_location)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить доступность регистрации")
async def edit_event_enable_registration(message: Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.button(text="Да")
    builder.button(text="Нет")
    builder.button(text="Отмена")
    builder.adjust(1)
    await message.answer("Доступна ли регистрация на мероприятие?", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(EditEventForm.waiting_for_enable_registration)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить или отключить ссылку на регистрацию")
async def edit_event_registration_url(message: Message, state: FSMContext):
    await message.answer("Введите новую ссылку на регистрацию (или 'отключить' для удаления):", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_registration_url)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить доступность билетов")
async def edit_event_enable_tickets(message: Message, state: FSMContext):
    builder = ReplyKeyboardBuilder()
    builder.button(text="Да")
    builder.button(text="Нет")
    builder.button(text="Отмена")
    builder.adjust(1)
    await message.answer("Доступна ли покупка билетов на мероприятие?", reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(EditEventForm.waiting_for_enable_tickets)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить или отключить ссылку на покупку билета")
async def edit_event_ticket_url(message: Message, state: FSMContext):
    await message.answer("Введите новую ссылку на покупку билета (или 'отключить' для удаления):", reply_markup=cancel_keyboard())
    await state.set_state(EditEventForm.waiting_for_ticket_url)

@admin_event_router.message(EditEventForm.waiting_for_title)
async def process_event_title(message: Message, state: FSMContext):
    new_title = message.text.strip()
    if not new_title:
        await message.answer("Название не может быть пустым.", reply_markup=cancel_keyboard())
        return
    if check_length(new_title, 100):
        await message.answer("Название слишком длинное. Максимальная длина - 100 символов.", reply_markup=cancel_keyboard())
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

@admin_event_router.message(EditEventForm.waiting_for_description)
async def process_event_description(message: Message, state: FSMContext):
    new_description = message.text.strip()
    if not new_description:
        await message.answer("Описание не может быть пустым.", reply_markup=cancel_keyboard())
        return
    if check_length(new_description, 100):
        await message.answer("Описание слишком длинное. Максимальная длина - 100 символов.", reply_markup=cancel_keyboard())
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

@admin_event_router.message(EditEventForm.waiting_for_info)
async def process_event_info(message: Message, state: FSMContext):
    new_info = message.text.strip()
    if not new_info:
        await message.answer("Информация не может быть пустой.", reply_markup=cancel_keyboard())
        return
    if check_length(new_info, 400):
        await message.answer("Информация слишком длинная. Максимальная длина - 400 символов.", reply_markup=cancel_keyboard())
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

@admin_event_router.message(EditEventForm.waiting_for_location)
async def process_event_location(message: Message, state: FSMContext):
    new_location = message.text.strip()
    if not new_location:
        await message.answer("Локация не может быть пустой.", reply_markup=cancel_keyboard())
        return
    if check_length(new_location, 100):
        await message.answer("Локация слишком длинная. Максимальная длина - 100 символов.", reply_markup=cancel_keyboard())
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

@admin_event_router.message(EditEventForm.waiting_for_enable_registration)
async def process_edit_enable_registration(message: Message, state: FSMContext):
    choice = message.text.strip().lower()
    logger.debug(f"User {message.from_user.id} sent choice '{choice}' for enable_registration")
    if choice not in ["да", "нет"]:
        logger.warning(f"Invalid choice for enable_registration: '{choice}' by user {message.from_user.id}")
        await message.answer(
            "Пожалуйста, выберите 'Да' или 'Нет':",
            reply_markup=ReplyKeyboardBuilder().add(
                {"text": "Да"}, {"text": "Нет"}, {"text": "Отмена"}
            ).adjust(1).as_markup(resize_keyboard=True)
        )
        return
    enable_registration = choice == "да"
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка доступа к мероприятию.", reply_markup=events_management_keyboard())
        await state.clear()
        return
    updated_fields = {"enable_registration": enable_registration}
    if not enable_registration:
        updated_fields["registration_url"] = None
    updated_event = await update_event(event_id=event["id"], updated_fields=updated_fields, bot=None)
    if updated_event:
        logger.info(f"Event {event['id']} enable_registration updated to {enable_registration}")
        event["enable_registration"] = enable_registration
        if not enable_registration:
            event["registration_url"] = None
        await state.update_data(event=event)
        if enable_registration:
            await state.set_state(EditEventForm.waiting_for_registration_url)
            await message.answer("Введите новую ссылку на регистрацию:", reply_markup=cancel_keyboard())
        else:
            await message.answer("Доступность регистрации обновлена.", reply_markup=edit_event_keyboard())
            await state.set_state(EditEventForm.choosing_field)
    else:
        logger.error(f"Failed to update enable_registration for event {event['id']}")
        await message.answer("Ошибка при обновлении доступности регистрации. Попробуйте снова.", reply_markup=edit_event_keyboard())

@admin_event_router.message(EditEventForm.waiting_for_registration_url)
async def process_event_registration_url(message: Message, state: FSMContext):
    new_url = message.text.strip()
    logger.debug(f"User {message.from_user.id} sent registration_url '{new_url}'")
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка доступа к мероприятию.", reply_markup=events_management_keyboard())
        await state.clear()
        return
    if new_url.lower() == "отключить":
        updated_fields = {"registration_url": None, "enable_registration": False}
    else:
        if check_length(new_url, 70):
            await message.answer("Ссылка слишком длинная. Максимальная длина - 70 символов.", reply_markup=cancel_keyboard())
            return
        if not URL_PATTERN.match(new_url):
            logger.warning(f"Invalid URL: '{new_url}' by user {message.from_user.id}")
            await message.answer("Неверный формат ссылки. Введите корректную ссылку или 'отключить':", reply_markup=cancel_keyboard())
            return
        updated_fields = {"registration_url": new_url}
    updated_event = await update_event(event_id=event["id"], updated_fields=updated_fields, bot=None)
    if updated_event:
        logger.info(f"Registration URL updated for event {event['id']}")
        event["registration_url"] = updated_fields.get("registration_url")
        event["enable_registration"] = updated_fields.get("enable_registration", event["enable_registration"])
        await state.update_data(event=event)
        await message.answer("Ссылка на регистрацию обновлена.", reply_markup=edit_event_keyboard())
        await state.set_state(EditEventForm.choosing_field)
    else:
        logger.error(f"Failed to update registration URL for event {event['id']}")
        await message.answer("Ошибка при обновлении ссылки на регистрацию. Попробуйте снова.", reply_markup=edit_event_keyboard())

@admin_event_router.message(EditEventForm.waiting_for_enable_tickets)
async def process_edit_enable_tickets(message: Message, state: FSMContext):
    choice = message.text.strip().lower()
    logger.debug(f"User {message.from_user.id} sent choice '{choice}' for enable_tickets")
    if choice not in ["да", "нет"]:
        logger.warning(f"Invalid choice for enable_tickets: '{choice}' by user {message.from_user.id}")
        await message.answer(
            "Пожалуйста, выберите 'Да' или 'Нет':",
            reply_markup=ReplyKeyboardBuilder().add(
                {"text": "Да"}, {"text": "Нет"}, {"text": "Отмена"}
            ).adjust(1).as_markup(resize_keyboard=True)
        )
        return
    enable_tickets = choice == "да"
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка доступа к мероприятию.", reply_markup=events_management_keyboard())
        await state.clear()
        return
    updated_fields = {"enable_tickets": enable_tickets}
    if not enable_tickets:
        updated_fields["ticket_url"] = None
    else:
        if not event.get("ticket_url"):
            await state.set_state(EditEventForm.waiting_for_ticket_url)
            await message.answer("Введите ссылку на покупку билета:", reply_markup=cancel_keyboard())
            return
        updated_fields["ticket_url"] = event.get("ticket_url")
    updated_event = await update_event(event_id=event["id"], updated_fields=updated_fields, bot=None)
    if updated_event:
        logger.info(f"Event {event['id']} enable_tickets updated to {enable_tickets}")
        event["enable_tickets"] = enable_tickets
        if not enable_tickets:
            event["ticket_url"] = None
        else:
            event["ticket_url"] = updated_fields.get("ticket_url")
        await state.update_data(event=event)
        await message.answer("Доступность билетов обновлена.", reply_markup=edit_event_keyboard())
        await state.set_state(EditEventForm.choosing_field)
    else:
        logger.error(f"Failed to update enable_tickets for event {event['id']}")
        await message.answer("Ошибка при обновлении доступности билетов. Попробуйте снова.", reply_markup=edit_event_keyboard())

@admin_event_router.message(EditEventForm.waiting_for_ticket_url)
async def process_event_ticket_url(message: Message, state: FSMContext):
    new_url = message.text.strip()
    logger.debug(f"User {message.from_user.id} sent ticket_url '{new_url}'")
    data = await state.get_data()
    event = data.get("event")
    if not event:
        logger.error(f"No event data found")
        await message.answer("Ошибка доступа к мероприятию.", reply_markup=events_management_keyboard())
        await state.clear()
        return
    if new_url.lower() == "отключить":
        updated_fields = {"ticket_url": None, "enable_tickets": False}
    else:
        if check_length(new_url, 70):
            await message.answer("Ссылка слишком длинная. Максимальная длина - 70 символов.", reply_markup=cancel_keyboard())
            return
        if not URL_PATTERN.match(new_url):
            logger.warning(f"Invalid URL: '{new_url}' by user {message.from_user.id}")
            await message.answer("Неверный формат ссылки. Введите корректную ссылку или 'отключить':", reply_markup=cancel_keyboard())
            return
        updated_fields = {"ticket_url": new_url, "enable_tickets": True}
    updated_event = await update_event(event_id=event["id"], updated_fields=updated_fields, bot=None)
    if updated_event:
        logger.info(f"Ticket URL updated for event {event['id']}")
        event["ticket_url"] = updated_fields.get("ticket_url")
        event["enable_tickets"] = updated_fields.get("enable_tickets", event["enable_tickets"])
        await state.update_data(event=event)
        await message.answer("Ссылка на покупку билета обновлена.", reply_markup=edit_event_keyboard())
        await state.set_state(EditEventForm.choosing_field)
    else:
        logger.error(f"Failed to update ticket URL for event {event['id']}")
        await message.answer("Ошибка при обновлении ссылки на покупку билета. Попробуйте снова.", reply_markup=edit_event_keyboard())

# =================================================================================================
# Обработчики удаления мероприятий
# =================================================================================================
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
        f"{event['title']}\n"
        f"{event['description']}\n"
        f"{event['info']}\n"
        f"{format_datetime(event.get('start_date'))} - {format_datetime(event.get('end_date'))}\n"
        f"{event['location']}\n"
        f"Регистрация: {'Включена' if event['enable_registration'] else 'Выключена'}\n"
        f"Ссылка на регистрация: {event.get('registration_url') or 'Отсутствует'}\n"
        f"Покупка билетов: {'Включена' if event['enable_tickets'] else 'Выключена'}\n"
        f"Ссылка на покупку билета: {event.get('ticket_url') or 'Отсутствует'}"
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