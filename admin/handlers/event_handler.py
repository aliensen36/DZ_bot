import aiohttp
import base64
import logging
from io import BytesIO
from datetime import datetime, timezone
from aiogram import F, Router
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from data.config import config_settings
from admin.keyboards.admin_reply import events_management_keyboard, admin_keyboard, cancel_keyboard, edit_event_keyboard
from data.url import url_event
from utils.filters import ChatTypeFilter, IsGroupAdmin, ADMIN_CHAT_ID

# Настройка логирования
logger = logging.getLogger(__name__)

admin_event_router = Router()
admin_event_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([ADMIN_CHAT_ID], show_message=False)
)

# Состояния для FSM
class EventForm(StatesGroup):
    waiting_for_title = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_info = State()
    waiting_for_start_date = State()
    waiting_for_end_date = State()
    waiting_for_location = State()

class EditEventForm(StatesGroup):
    choosing_field = State()
    waiting_for_title = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_info = State()
    waiting_for_start_date = State()
    waiting_for_end_date = State()
    waiting_for_location = State()


# Функция для форматирования даты и времени
def format_datetime(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt_str or "-"


# Хендлер для команды "Отмена"
@admin_event_router.message(F.text == "Отмена", StateFilter(EventForm))
async def cancel_event_creation(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Вы вернулись в меню мероприятий.", reply_markup=events_management_keyboard())


# Хендлер для кнопки "Назад" в главном меню администратора
@admin_event_router.message(F.text == "Назад")
async def back_to_admin_menu(message: Message):
    await message.answer(
        "Вы вернулись в главное меню администратора.",
        reply_markup=admin_keyboard()
    )


# Функция для создания нового мероприятия
async def create_new_event(event_data: dict, photo_file_id: str = None, bot=None):
    url = f"{url_event}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    payload = event_data.copy()

    if photo_file_id:
        payload["photo"] = photo_file_id
        print(f"Using Telegram file_id for photo: {photo_file_id}")
    else:
        payload["photo"] = ""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                print(f"Create event status: {response.status}")
                print(f"Payload sent: {payload}")
                print(f"Response headers: {response.headers}")
                if response.status == 201:
                    return await response.json()
                else:
                    error_text = await response.text()
                    print(f"Error creating event: {error_text}")
                    return None
    except aiohttp.ClientError as e:
        print(f"HTTP Client Error creating event: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error creating event: {e}")
        return None


# Хендлеры для управления мероприятиями
@admin_event_router.message(F.text == "🎉 Мероприятия")
async def handle_events(message: Message):
    await message.answer(
        "Управление мероприятиями:",
        reply_markup=events_management_keyboard()
    )


# Хендлеры для создания нового мероприятия
@admin_event_router.message(F.text == "Добавить мероприятие")
async def handle_add_event(message: Message, state: FSMContext):
    await state.set_state(EventForm.waiting_for_title)
    await message.answer(
        "Введите название мероприятия:",
        reply_markup=cancel_keyboard()
    )


# Хендлеры для обработки каждого шага создания мероприятия
@admin_event_router.message(StateFilter(EventForm.waiting_for_title))
async def process_event_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым. Пожалуйста, введите название мероприятия:", reply_markup=cancel_keyboard())
        return
    await state.update_data(title=title)
    await state.set_state(EventForm.waiting_for_photo)
    await message.answer("Отправьте фото для мероприятия:", reply_markup=cancel_keyboard())


# Хендлеры для обработки фото мероприятия
@admin_event_router.message(StateFilter(EventForm.waiting_for_photo))
async def process_event_photo(message: Message, state: FSMContext):
    print(f"Received message in waiting_for_photo: type={message.content_type}, text={message.text}, photo={message.photo}")
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        print(f"Photo received: file_id={photo_file_id}, size={message.photo[-1].file_size}")
        if message.photo[-1].file_size > 10 * 1024 * 1024:
            await message.answer("Фото слишком большое. Максимальный размер: 10 МБ.", reply_markup=cancel_keyboard())
            return
        await state.update_data(photo=photo_file_id)
        await state.set_state(EventForm.waiting_for_description)
        await message.answer("Фото получено. Введите описание мероприятия:", reply_markup=cancel_keyboard())
    else:
        await message.answer("Пожалуйста, отправьте фото.", reply_markup=cancel_keyboard())


# Хендлеры для обработки описания мероприятия
@admin_event_router.message(StateFilter(EventForm.waiting_for_description))
async def process_event_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if not description:
        await message.answer("Описание не может быть пустым. Пожалуйста, введите описание мероприятия:", reply_markup=cancel_keyboard())
        return
    await state.update_data(description=description)
    await state.set_state(EventForm.waiting_for_info)
    await message.answer("Введите дополнительную информацию о мероприятии:", reply_markup=cancel_keyboard())


# Хендлеры для обработки дополнительной информации о мероприятии
@admin_event_router.message(StateFilter(EventForm.waiting_for_info))
async def process_event_info(message: Message, state: FSMContext):
    info = message.text.strip()
    if not info:
        await message.answer("Информация не может быть пустой. Пожалуйста, введите дополнительную информацию:", reply_markup=cancel_keyboard())
        return
    await state.update_data(info=info)
    await state.set_state(EventForm.waiting_for_start_date)
    await message.answer("Введите дату и время начала мероприятия (формат YYYY-MM-DD HH:MM, например, 2025-07-06 15:30):", reply_markup=cancel_keyboard())


# Хендлеры для обработки даты и времени начала мероприятия
@admin_event_router.message(StateFilter(EventForm.waiting_for_start_date))
async def process_start_date(message: Message, state: FSMContext):
    try:
        start_date = datetime.strptime(message.text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        current_time = datetime.now(timezone.utc)
        if start_date < current_time:
            await message.answer("Дата и время начала не могут быть в прошлом. Пожалуйста, введите дату и время в будущем (формат YYYY-MM-DD HH:MM, например, 2025-07-06 15:30).", reply_markup=cancel_keyboard())
            return
        await state.update_data(start_date=start_date)
        await state.set_state(EventForm.waiting_for_end_date)
        await message.answer(f"Дата и время начала ({message.text}) успешно сохранены. Введите дату и время окончания (формат YYYY-MM-DD HH:MM):", reply_markup=cancel_keyboard())
    except ValueError:
        await message.answer("Неверный формат даты и времени. Пожалуйста, используйте формат YYYY-MM-DD HH:MM (например, 2025-07-06 15:30).", reply_markup=cancel_keyboard())


# Хендлеры для обработки даты и времени окончания мероприятия
@admin_event_router.message(StateFilter(EventForm.waiting_for_end_date))
async def process_end_date(message: Message, state: FSMContext):
    try:
        end_date = datetime.strptime(message.text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        data = await state.get_data()
        start_date = data.get("start_date")
        if end_date <= start_date:
            await message.answer("Дата и время окончания должны быть позже даты и времени начала. Пожалуйста, введите корректную дату и время окончания (формат YYYY-MM-DD HH:MM).", reply_markup=cancel_keyboard())
            return
        await state.update_data(end_date=end_date)
        await state.set_state(EventForm.waiting_for_location)
        await message.answer("Введите место проведения мероприятия:", reply_markup=cancel_keyboard())
    except ValueError:
        await message.answer("Неверный формат даты и времени. Пожалуйста, используйте формат YYYY-MM-DD HH:MM (например, 2025-07-06 15:30).", reply_markup=cancel_keyboard())


# Хендлеры для обработки места проведения мероприятия и создания мероприятия
@admin_event_router.message(StateFilter(EventForm.waiting_for_location))
async def process_event_location_and_create(message: Message, state: FSMContext, bot):
    location = message.text.strip()
    if not location:
        await message.answer("Место проведения не может быть пустым. Пожалуйста, введите место проведения мероприятия:", reply_markup=cancel_keyboard())
        return
    await state.update_data(location=location)
    data = await state.get_data()
    event_data = {
        "title": data.get("title"),
        "description": data.get("description"),
        "info": data.get("info"),
        "start_date": data.get("start_date").isoformat(),
        "end_date": data.get("end_date").isoformat(),
        "location": data.get("location")
    }
    photo_file_id = data.get("photo")
    created_event = await create_new_event(event_data, photo_file_id, bot)
    if created_event:

        await message.answer_photo(
            caption = (
            f"Мероприятие успешно создано!\n"
            f"Название: {event_data['title']}\n"
            f"Описание: {event_data['description']}\n"
            f"Информация: {event_data['info']}\n"
            f"Дата начала: {format_datetime(event_data.get('start_date'))}\n"
            f"Дата окончания: {format_datetime(event_data.get('end_date'))}\n"
            f"Место: {event_data['location']}"
            ),
            photo=created_event.get("photo", None),
            reply_markup=events_management_keyboard(),
        )
        await state.clear()
    else:
        await message.answer(
            "Произошла ошибка при создании мероприятия. Пожалуйста, проверьте данные и попробуйте еще раз.",
            reply_markup=events_management_keyboard()
        )
        await state.clear()

# Получение списка мероприятий
async def fetch_events() -> list:
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_event}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Fetched events data: {data}")
                    return data 
                else:
                    logger.warning(f"Failed to fetch events, status={resp.status}")
                    return []
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching events: {e}")
        return []
    

# Функция для получения мероприятия по названию
async def get_event_by_title(title: str) -> dict:
    events = await fetch_events()
    for event in events:
        if event.get("title") == title:
            return event
    return None

    
# Функция для обновления мероприятия
async def update_event(event_id: int, updated_fields: dict) -> bool:
    url = f"{url_event.rstrip('/')}/{event_id}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    logger.info(f"Updating event data for event_id={event_id} with fields={updated_fields}, url={url}")

    try:
        # Получаем текущие данные мероприятия
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp_get:
                if resp_get.status != 200:
                    logger.error(f"Failed to fetch current event data for event_id={event_id}: status={resp_get.status}")
                    return False
                current_data = await resp_get.json()

                # Сравниваем текущие данные с updated_fields
                update_needed = False
                for key, value in updated_fields.items():
                    if value is not None and current_data.get(key) != value:
                        update_needed = True
                        break

                if not update_needed:
                    logger.info(f"No changes needed for event_id={event_id}")
                    return True

                # Выполняем обновление только если есть изменения
                async with session.patch(url, json=updated_fields, headers=headers) as resp:
                    response_text = await resp.text()
                    if resp.status in [200, 204]:
                        logger.info(f"Event data updated for event_id={event_id}, status={resp.status}")
                        return True
                    else:
                        logger.error(
                            f"Failed to update event data for event_id={event_id}: status={resp.status}, response={response_text}"
                        )
                        return False

    except aiohttp.ClientError as e:
        logger.exception(f"Client error while updating event data for event_id={event_id}: {str(e)}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error while updating event data for event_id={event_id}: {str(e)}")
        return False

# Хендлеры для редактирования мероприятий
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


# Хендлер для выбора мероприятия для редактирования
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
        f"Место: {event['location']}"
    )

    await message.answer_photo(
        caption=current_event_text,
        photo=event.get("photo", None),
        reply_markup=edit_event_keyboard()
    )


@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить название")
async def edit_event_title(message: Message, state: FSMContext):
    await message.answer("Введите новое название:")
    await state.set_state(EditEventForm.waiting_for_title)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить фото")
async def edit_event_photo(message: Message, state: FSMContext):
    await message.answer("Отправьте новое фото события:")
    await state.set_state(EditEventForm.waiting_for_photo)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить описание")
async def edit_event_description(message: Message, state: FSMContext):
    await message.answer("Введите новое описание события:")
    await state.set_state(EditEventForm.waiting_for_description)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить информацию")
async def edit_event_info(message: Message, state: FSMContext):
    await message.answer("Введите новую информацию о событии:")
    await state.set_state(EditEventForm.waiting_for_info)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить дату начала")
async def edit_event_start_date(message: Message, state: FSMContext):
    await message.answer("Введите новую дату начала события (в формате ГГГГ-ММ-ДД ЧЧ:ММ):")
    await state.set_state(EditEventForm.waiting_for_start_date)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить дату окончания")
async def edit_event_end_date(message: Message, state: FSMContext):
    await message.answer("Введите новую дату окончания события (в формате ГГГГ-ММ-ДД ЧЧ:ММ):")
    await state.set_state(EditEventForm.waiting_for_end_date)

@admin_event_router.message(EditEventForm.choosing_field, F.text == "Изменить локацию")
async def edit_event_location(message: Message, state: FSMContext):
    await message.answer("Введите новую локацию события:")
    await state.set_state(EditEventForm.waiting_for_location)


@admin_event_router.message(EditEventForm.waiting_for_title)
async def process_event_title(message: Message, state: FSMContext):
    new_title = message.text.strip()
    if not new_title:
        await message.answer("Название не может быть пустым.")
        return
    data = await state.get_data()
    event = data.get("event")
    if not event:
        await message.answer("Ошибка доступа к событию.")
        return
    await update_event(event_id=event["id"], updated_fields={"title": new_title})
    event["title"] = new_title
    await state.update_data(event=event)
    await message.answer("Название мероприятия обновлено.", reply_markup=edit_event_keyboard())
    await state.set_state(EditEventForm.choosing_field)


@admin_event_router.message(EditEventForm.waiting_for_photo)
async def process_event_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    event = data.get("event")
    if not event:
        await message.answer("Ошибка доступа к событию.")
        return

    if message.photo:
        photo_file_id = message.photo[-1].file_id
        if message.photo[-1].file_size > 10 * 1024 * 1024:
            await message.answer("Фото слишком большое. Максимум 10 МБ.")
            return
        await update_event(event_id=event["id"], updated_fields={"photo": photo_file_id})
        event["photo"] = photo_file_id
        await state.update_data(event=event)
        await message.answer("Фото события обновлено.", reply_markup=edit_event_keyboard())
    else:
        await message.answer("Пожалуйста, отправьте изображение.")

    await state.set_state(EditEventForm.choosing_field)

@admin_event_router.message(EditEventForm.waiting_for_description)
async def process_event_description(message: Message, state: FSMContext):
    new_description = message.text.strip()
    if not new_description:
        await message.answer("Описание не может быть пустым.")
        return

    data = await state.get_data()
    event = data.get("event")
    if not event:
        await message.answer("Ошибка доступа к событию.")
        return

    await update_event(event_id=event["id"], updated_fields={"description": new_description})
    event["description"] = new_description
    await state.update_data(event=event)
    await message.answer("Описание события обновлено.", reply_markup=edit_event_keyboard())

    await state.set_state(EditEventForm.choosing_field)

@admin_event_router.message(EditEventForm.waiting_for_info)
async def process_event_info(message: Message, state: FSMContext):
    new_info = message.text.strip()
    if not new_info:
        await message.answer("Информация не может быть пустой.")
        return

    data = await state.get_data()
    event = data.get("event")
    if not event:
        await message.answer("Ошибка доступа к событию.")
        return

    await update_event(event_id=event["id"], updated_fields={"info": new_info})
    event["info"] = new_info 
    await state.update_data(event=event)
    await message.answer("Информация о событии обновлена.", reply_markup=edit_event_keyboard())

    await state.set_state(EditEventForm.choosing_field)

@admin_event_router.message(EditEventForm.waiting_for_start_date)
async def process_event_start_date(message: Message, state: FSMContext):
    new_start_date = message.text.strip()
    try:
        start_date = datetime.strptime(new_start_date, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        if start_date < datetime.now(timezone.utc):
            await message.answer("Дата начала не может быть в прошлом.", reply_markup=cancel_keyboard())
            return

        data = await state.get_data()
        event = data.get("event")
        if not event:
            await message.answer("Ошибка доступа к событию.")
            return

        await update_event(event_id=event["id"], updated_fields={"start_date": new_start_date})
        event["start_date"] = new_start_date
        await state.update_data(event=event)
        await message.answer("Дата начала обновлена.", reply_markup=edit_event_keyboard())

        await state.set_state(EditEventForm.choosing_field)
    except ValueError:
        await message.answer("Неверный формат даты. Пример: 2025-07-06 15:30", reply_markup=cancel_keyboard())

@admin_event_router.message(EditEventForm.waiting_for_end_date)
async def process_event_end_date(message: Message, state: FSMContext):
    new_end_date = message.text.strip()
    try:
        end_date = datetime.strptime(new_end_date, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        data = await state.get_data()
        event = data.get("event")
        if not event:
            await message.answer("Ошибка доступа к событию.")
            return

        start_date_str = event.get("start_date")
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if end_date <= start_date:
                await message.answer("Дата окончания должна быть позже начала.", reply_markup=cancel_keyboard())
                return

        await update_event(event_id=event["id"], updated_fields={"end_date": new_end_date})
        event["end_date"] = new_end_date
        await state.update_data(event=event)
        await message.answer("Дата окончания обновлена.", reply_markup=edit_event_keyboard())

        await state.set_state(EditEventForm.choosing_field)
    except ValueError:
        await message.answer("Неверный формат даты. Пример: 2025-07-06 15:30", reply_markup=cancel_keyboard())

@admin_event_router.message(EditEventForm.waiting_for_location)
async def process_event_location(message: Message, state: FSMContext):
    new_location = message.text.strip()
    if not new_location:
        await message.answer("Локация не может быть пустой.")
        return

    data = await state.get_data()
    event = data.get("event")
    if not event:
        await message.answer("Ошибка доступа к событию.")
        return

    await update_event(event_id=event["id"], updated_fields={"location": new_location})
    event["location"] = new_location
    await state.update_data(event=event)
    await message.answer("Локация обновлена.", reply_markup=edit_event_keyboard())

    await state.set_state(EditEventForm.choosing_field)


async def delete_event(event_id: int) -> bool:
    url = f"{url_event}{event_id}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as resp:
                return resp.status in (200, 204)
    except Exception as e:
        logger.error(f"Failed to update event {event_id}: {e}")
        return False


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

    # Показываем информацию о мероприятии и кнопки для подтверждения удаления
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

    await message.answer_photo(
        caption=f"Вы выбрали мероприятие:\n\n{current_event_text}\n\nВы действительно хотите удалить это мероприятие?",
        photo=event.get("photo", None),
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@admin_event_router.message(F.text == "Удалить")
async def confirm_delete_event(message: Message, state: FSMContext):
    data = await state.get_data()
    event = data.get("event")

    if not event:
        await message.answer("Ошибка: событие не найдено.")
        return

    success = await delete_event(event_id=event["id"])

    if success:
        await message.answer("Мероприятие успешно удалено.", reply_markup=events_management_keyboard())
    else:
        await message.answer("Не удалось удалить мероприятие. Попробуйте снова.", reply_markup=events_management_keyboard())

    await state.clear()