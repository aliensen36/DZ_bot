import re
import logging
from datetime import datetime, timezone
import aiohttp
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from data.config import config_settings
from data.url import url_promotions

from resident_admin.keyboards.res_admin_reply import res_admin_promotion_keyboard, res_admin_keyboard, res_admin_cancel_keyboard, res_admin_edit_promotion_keyboard
from utils.filters import ChatTypeFilter, IsGroupAdmin, RESIDENT_ADMIN_CHAT_ID
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import logging

logger = logging.getLogger(__name__)

RA_promotion_router = Router()
RA_promotion_router.message.filter(
    ChatTypeFilter("private"),
    IsGroupAdmin([RESIDENT_ADMIN_CHAT_ID], show_message=False)
)

URL_PATTERN = re.compile(
    r'^(https?://)?'                  # optional http or https
    r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}' # domain
    r'(:\d+)?'                        # optional port
    r'(/[\w\-._~:/?#[\]@!$&\'()*+,;=]*)?$'  # path + query
)

DISCOUNT_PATTERN = re.compile(r'^\s*скидка\s*(\d+\.?\d*)\s*%?\s*$', re.IGNORECASE)
BONUS_PATTERN = re.compile(r'^\s*бонус(?:ов)?\s*(\d+\.?\d*)\s*$', re.IGNORECASE)

# Состояния для FSM
class PromotionForm(StatesGroup):
    waiting_for_title = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_start_date = State()
    waiting_for_end_date = State()
    waiting_for_discount_or_bonus = State()
    waiting_for_url = State()

class PromotionEditForm(StatesGroup):
    choosing_field = State()
    waiting_for_title = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_start_date = State()
    waiting_for_end_date = State()
    waiting_for_discount_or_bonus = State()
    waiting_for_url = State()


# Хендлер для команды "Сбросить"
@RA_promotion_router.message(F.text == "Сбросить", StateFilter(PromotionForm))
async def cancel_promotion_creation(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Вы вернулись в меню акций.", reply_markup=res_admin_promotion_keyboard())


# Хендлер для кнопки "↩ Обратно" в главном меню администратора
@RA_promotion_router.message(F.text == "↩ Обратно")
async def back_to_res_admin_menu(message: Message):
    await message.answer(
        "Вы вернулись в главное меню администратора.",
        reply_markup=res_admin_keyboard()
    )


# Функция для форматирования даты и времени
def format_datetime(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt_str or "-"
    

# Создание новой акции
async def create_new_promotion(promotion_data: dict, photo_file_id: str = None, resident_id: int = None, bot=None):
    url = f"{url_promotions}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    payload = promotion_data.copy()

    payload["resident"] = resident_id

    if photo_file_id:
        payload["photo"] = photo_file_id
        print(f"Using Telegram file_id for photo: {photo_file_id}")
    else:
        payload["photo"] = ""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                print(f"Create promotion status: {response.status}")
                print(f"Payload sent: {payload}")
                print(f"Response headers: {response.headers}")
                if response.status == 201:
                    return await response.json()
                else:
                    error_text = await response.text()
                    print(f"Error creating promotion: {error_text}")
                    return None
    except aiohttp.ClientError as e:
        print(f"HTTP Client Error creating promotion: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error creating promotion: {e}")
        return None


# Хендлер для кнопки "Акции"
@RA_promotion_router.message(F.text == "Акции")
async def handle_promotions(message: Message):
    await message.answer(
        "Управление акциями:",
        reply_markup=res_admin_promotion_keyboard()
    )

# Хендлеры для создания новой акции
@RA_promotion_router.message(F.text == "Создать акцию")
async def handle_add_promotion(message: Message, state: FSMContext):
    await state.set_state(PromotionForm.waiting_for_title)
    await message.answer(
        "Введите название акции:",
        reply_markup=res_admin_cancel_keyboard()
    )


# Хендлеры для обработки каждого шага создания акции
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_title))
async def process_promotion_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым. Пожалуйста, введите название акции:", reply_markup=res_admin_cancel_keyboard())
        return
    await state.update_data(title=title)
    await state.set_state(PromotionForm.waiting_for_photo)
    await message.answer("Отправьте фото для мероприятия:", reply_markup=res_admin_cancel_keyboard())


# Хендлеры для обработки фото акции
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_photo))
async def process_promotion_photo(message: Message, state: FSMContext):
    print(f"Received message in waiting_for_photo: type={message.content_type}, text={message.text}, photo={message.photo}")
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        print(f"Photo received: file_id={photo_file_id}, size={message.photo[-1].file_size}")
        if message.photo[-1].file_size > 10 * 1024 * 1024:
            await message.answer("Фото слишком большое. Максимальный размер: 10 МБ.", reply_markup=res_admin_cancel_keyboard())
            return
        await state.update_data(photo=photo_file_id)
        await state.set_state(PromotionForm.waiting_for_description)
        await message.answer("Фото получено. Введите описание мероприятия:", reply_markup=res_admin_cancel_keyboard())
    else:
        await message.answer("Пожалуйста, отправьте фото.", reply_markup=res_admin_cancel_keyboard())


# Хендлеры для обработки описания акции
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_description))
async def process_promotion_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if not description:
        await message.answer("Описание не может быть пустым. Пожалуйста, введите описание акции:", reply_markup=res_admin_cancel_keyboard())
        return
    await state.update_data(description=description)
    await state.set_state(PromotionForm.waiting_for_start_date)
    await message.answer("Введите дату и время начала мероприятия (формат YYYY-MM-DD HH:MM, например, 2025-07-06 15:30):", reply_markup=res_admin_cancel_keyboard())   


# Хендлеры для обработки даты и времени начала акции
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_start_date))
async def process_promotion_start_date(message: Message, state: FSMContext):
    try:
        start_date = datetime.strptime(message.text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        current_time = datetime.now(timezone.utc)
        if start_date < current_time:
            await message.answer("Дата и время начала не могут быть в прошлом. Пожалуйста, введите дату и время в будущем (формат YYYY-MM-DD HH:MM, например, 2025-07-06 15:30).", reply_markup=res_admin_cancel_keyboard())
            return
        await state.update_data(start_date=start_date)
        await state.set_state(PromotionForm.waiting_for_end_date)
        await message.answer(f"Дата и время начала ({message.text}) успешно сохранены. Введите дату и время окончания (формат YYYY-MM-DD HH:MM):", reply_markup=res_admin_cancel_keyboard())
    except ValueError:
        await message.answer("Неверный формат даты и времени. Пожалуйста, используйте формат YYYY-MM-DD HH:MM (например, 2025-07-06 15:30).", reply_markup=res_admin_cancel_keyboard())


# Хендлеры для обработки даты и времени окончания мероприятия
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_end_date))
async def process_promotion_end_date(message: Message, state: FSMContext):
    try:
        end_date = datetime.strptime(message.text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        data = await state.get_data()
        start_date = data.get("start_date")
        if end_date <= start_date:
            await message.answer(
                "Дата и время окончания должны быть позже даты и времени начала. Пожалуйста, введите корректную дату и время окончания (формат YYYY-MM-DD HH:MM).",
                reply_markup=res_admin_cancel_keyboard()
            )
            return
        await state.update_data(end_date=end_date)
        await state.set_state(PromotionForm.waiting_for_discount_or_bonus)
        await message.answer(
            "Введите скидку или бонус в формате 'Скидка 10%' или 'Бонусов 500':",
            reply_markup=res_admin_cancel_keyboard()
        )
    except ValueError:
        await message.answer(
            "Неверный формат даты и времени. Пожалуйста, используйте формат YYYY-MM-DD HH:MM (например, 2025-07-06 15:30).",
            reply_markup=res_admin_cancel_keyboard()
        )


# Хендлеры для обработки скидки или бонуса
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_discount_or_bonus))
async def process_discount_or_bonus(message: Message, state: FSMContext, bot):
    input_text = message.text.strip().lower()
    
    discount_match = DISCOUNT_PATTERN.match(input_text)
    bonus_match = BONUS_PATTERN.match(input_text)

    if discount_match:
        discount_value = float(discount_match.group(1))
        if discount_value <= 0 or discount_value > 100:
            await message.answer(
                "Значение скидки должно быть от 0 до 100%. Введите корректное значение, например 'Скидка 10%':",
                reply_markup=res_admin_cancel_keyboard()
            )
            return
        await state.update_data(discount_or_bonus="скидка", discount_or_bonus_value=discount_value)
    elif bonus_match:
        bonus_value = float(bonus_match.group(1))
        if bonus_value <= 0:
            await message.answer(
                "Значение бонуса должно быть больше 0. Введите корректное значение, например 'Бонусов 500':",
                reply_markup=res_admin_cancel_keyboard()
            )
            return
        await state.update_data(discount_or_bonus="бонус", discount_or_bonus_value=bonus_value)
    else:
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

# Хендлеры для обработки ссылки на участие в акции и создание акции
@RA_promotion_router.message(StateFilter(PromotionForm.waiting_for_url))
async def process_promotion_url_and_create(message: Message, state: FSMContext, bot):
    url = message.text.strip()
    if not url:
        await message.answer(
            "Ссылка для участия в акции не может быть пустой. Пожалуйста, введите ссылку:",
            reply_markup=res_admin_cancel_keyboard()
        )
        return
    if not URL_PATTERN.match(url):
        await message.answer(
            "Неверный формат ссылки. Пожалуйста, введите корректную ссылку для участия:",
            reply_markup=res_admin_cancel_keyboard()
        )
        return
    await state.update_data(url=url)

    # Извлекаем данные из состояния FSM
    data = await state.get_data()

    # Проверяем, есть ли resident_id в состоянии
    resident_id = data.get("resident_id")
    if not resident_id:
        logger.error(f"Resident ID not found for user_id={message.from_user.id}")
        await message.answer(
            "Ошибка: не удалось определить ID резидента. Пожалуйста, войдите в админ-панель заново с помощью команды /res_admin.",
            reply_markup=res_admin_promotion_keyboard()
        )
        await state.clear()
        return

    # Формируем данные для отправки в API
    promotion_data = {
        "title": data.get("title"),
        "description": data.get("description"),
        "start_date": data.get("start_date").isoformat(),
        "end_date": data.get("end_date").isoformat(),
        "url": data.get("url"),
        "discount_or_bonus": data.get("discount_or_bonus"),
        "discount_or_bonus_value": data.get("discount_or_bonus_value"),
    }
    photo_file_id = data.get("photo")
    logger.info(f"Creating promotion with resident_id={resident_id} for user_id={message.from_user.id}")
    created_promotion = await create_new_promotion(promotion_data, photo_file_id, resident_id, bot)
    if created_promotion:
        await message.answer_photo(
            caption=(
                f"Акция успешно создана!\n"
                f"Название: {promotion_data['title']}\n"
                f"Описание: {promotion_data['description']}\n"
                f"Дата начала: {format_datetime(promotion_data.get('start_date'))}\n"
                f"Дата окончания: {format_datetime(promotion_data.get('end_date'))}\n"
                f"Ссылка для участия: {promotion_data['url']}\n"
                f"{promotion_data['discount_or_bonus'].capitalize()}: {promotion_data['discount_or_bonus_value']}{'%' if promotion_data['discount_or_bonus'] == 'скидка' else ''}\n"
                f"Ожидайте подтверждения от администратора."
            ),
            photo=created_promotion.get("photo", None),
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


# Хендлеры для получения списка акций
async def get_promotion_list(resident_id: int):
    url = f"{url_promotions}?resident={resident_id}"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Fetched promotions data: {data}")
                    return data 
                else:
                    logger.warning(f"Failed to fetch promotions, status={resp.status}")
                    return []
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching promotions: {e}")
        return []


# Хендлеры для отображения акции по названию
async def get_promotion_by_title(title: str) -> dict:
    promotions = await get_promotion_list()
    for promotion in promotions:
        if promotion.get("title") == title:
            return promotion
    return None


# Функция для обновления мероприятия
async def update_promotion(promotion_id: int, updated_fields: dict) -> bool:
    url = f"{url_promotions}{promotion_id}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    logger.info(f"Updating promotion data for promotion_id={promotion_id} with fields={updated_fields}, url={url}")

    try:
        # Получаем текущие данные мероприятия
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp_get:
                if resp_get.status != 200:
                    logger.error(f"Failed to fetch current promotion data for promotion_id={promotion_id}: status={resp_get.status}")
                    return False
                current_data = await resp_get.json()

                # Сравниваем текущие данные с updated_fields
                update_needed = False
                for key, value in updated_fields.items():
                    if value is not None and current_data.get(key) != value:
                        update_needed = True
                        break

                if not update_needed:
                    logger.info(f"No changes needed for promotion_id={promotion_id}")
                    return True

                # Выполняем обновление только если есть изменения
                async with session.patch(url, json=updated_fields, headers=headers) as resp:
                    response_text = await resp.text()
                    if resp.status in [200, 204]:
                        logger.info(f"Promotion data updated for promotion_id={promotion_id}, status={resp.status}")
                        return True
                    else:
                        logger.error(
                            f"Failed to update promotion data for promotion_id={promotion_id}: status={resp.status}, response={response_text}"
                        )
                        return False

    except aiohttp.ClientError as e:
        logger.exception(f"Client error while updating promotion data for promotion_id={promotion_id}: {str(e)}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error while updating promotion data for promotion_id={promotion_id}: {str(e)}")
        return False
    

# Хендлеры для редактирования мероприятий
@RA_promotion_router.message(F.text == "Изменить акцию")
async def edit_promotion_start(message: Message):
    promotions = await get_promotion_list()
    if not promotions:
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


# Хендлер для выбора мероприятия для редактирования
@RA_promotion_router.message(F.text.startswith("🖋️ "))
async def edit_promotion_select(message: Message, state: FSMContext):
    promotion_title = message.text[2:].strip()
    promotion = await get_promotion_by_title(promotion_title)

    if not promotion:
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

    await message.answer_photo(
        caption=current_promotion_text,
        photo=promotion.get("photo", None),
        reply_markup=res_admin_edit_promotion_keyboard()
    )


# Хендлеры для выбора поля для редактирования мероприятия
@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить название")
async def edit_promotion_title(message: Message, state: FSMContext):
    await message.answer("Введите новое название:")
    await state.set_state(PromotionEditForm.waiting_for_title)

@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить фото")
async def edit_promotion_photo(message: Message, state: FSMContext):
    await message.answer("Отправьте новое фото:")
    await state.set_state(PromotionEditForm.waiting_for_photo)

@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить описание")
async def edit_promotion_description(message: Message, state: FSMContext):
    await message.answer("Введите новое описание:")
    await state.set_state(PromotionEditForm.waiting_for_description)

@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить дату начала")
async def edit_promotion_start_date(message: Message, state: FSMContext):
    await message.answer("Введите новую дату начала (в формате ГГГГ-ММ-ДД ЧЧ:ММ):")
    await state.set_state(PromotionEditForm.waiting_for_start_date)

@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить дату окончания")
async def edit_promotion_end_date(message: Message, state: FSMContext):
    await message.answer("Введите новую дату окончания (в формате ГГГГ-ММ-ДД ЧЧ:ММ):")
    await state.set_state(PromotionEditForm.waiting_for_end_date)

@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить ссылку")
async def edit_promotion_url(message: Message, state: FSMContext):
    await message.answer("Введите новую ссылку:")
    await state.set_state(PromotionEditForm.waiting_for_url)

@RA_promotion_router.message(PromotionEditForm.choosing_field, F.text == "Изменить скидку/бонус")
async def edit_promotion_discount_or_bonus(message: Message, state: FSMContext):
    await message.answer(
        "Введите новую скидку или бонус в формате 'Скидка 10%' или 'Бонусов 500':",
        reply_markup=res_admin_cancel_keyboard()
    )
    await state.set_state(PromotionEditForm.waiting_for_discount_or_bonus)


# Хендлеры для обработки изменений в мероприятии
@RA_promotion_router.message(PromotionEditForm.waiting_for_title)
async def process_promotion_title(message: Message, state: FSMContext):
    new_title = message.text.strip()
    if not new_title:
        await message.answer("Название не может быть пустым.")
        return
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        await message.answer("Ошибка доступа к акции.")
        return
    await update_promotion(promotion_id=promotion["id"], updated_fields={"title": new_title})
    promotion["title"] = new_title
    await state.update_data(promotion=promotion)
    await message.answer("Название акции обновлено.", reply_markup=res_admin_edit_promotion_keyboard())
    await state.set_state(PromotionEditForm.choosing_field)


@RA_promotion_router.message(PromotionEditForm.waiting_for_photo)
async def process_promotion_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        await message.answer("Ошибка доступа к акции.")
        return

    if message.photo:
        photo_file_id = message.photo[-1].file_id
        if message.photo[-1].file_size > 10 * 1024 * 1024:
            await message.answer("Фото слишком большое. Максимум 10 МБ.")
            return
        await update_promotion(promotion_id=promotion["id"], updated_fields={"photo": photo_file_id})
        promotion["photo"] = photo_file_id
        await state.update_data(promotion=promotion)
        await message.answer("Фото акции обновлено.", reply_markup=res_admin_edit_promotion_keyboard())
    else:
        await message.answer("Пожалуйста, отправьте изображение.")

    await state.set_state(PromotionEditForm.choosing_field)

@RA_promotion_router.message(PromotionEditForm.waiting_for_description)
async def process_promotion_description(message: Message, state: FSMContext):
    new_description = message.text.strip()
    if not new_description:
        await message.answer("Описание не может быть пустым.")
        return

    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        await message.answer("Ошибка доступа к акции.")
        return

    await update_promotion(promotion_id=promotion["id"], updated_fields={"description": new_description})
    promotion["description"] = new_description
    await state.update_data(promotion=promotion)
    await message.answer("Описание акции обновлено.", reply_markup=res_admin_edit_promotion_keyboard())

    await state.set_state(PromotionEditForm.choosing_field)


@RA_promotion_router.message(PromotionEditForm.waiting_for_start_date)
async def process_promotion_start_date(message: Message, state: FSMContext):
    new_start_date = message.text.strip()
    try:
        start_date = datetime.strptime(new_start_date, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        if start_date < datetime.now(timezone.utc):
            await message.answer("Дата начала не может быть в прошлом.", reply_markup=res_admin_cancel_keyboard())
            return

        data = await state.get_data()
        promotion = data.get("promotion")
        if not promotion:
            await message.answer("Ошибка доступа к акции.")
            return

        await update_promotion(promotion_id=promotion["id"], updated_fields={"start_date": new_start_date})
        promotion["start_date"] = new_start_date
        await state.update_data(promotion=promotion)
        await message.answer("Дата начала обновлена.", reply_markup=res_admin_edit_promotion_keyboard())

        await state.set_state(PromotionEditForm.choosing_field)
    except ValueError:
        await message.answer("Неверный формат даты. Пример: 2025-07-06 15:30", reply_markup=res_admin_cancel_keyboard())

@RA_promotion_router.message(PromotionEditForm.waiting_for_end_date)
async def process_promotion_end_date(message: Message, state: FSMContext):
    new_end_date = message.text.strip()
    try:
        end_date = datetime.strptime(new_end_date, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        data = await state.get_data()
        promotion = data.get("promotion")
        if not promotion:
            await message.answer("Ошибка доступа к акции.")
            return

        start_date_str = promotion.get("start_date")
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if end_date <= start_date:
                await message.answer("Дата окончания должна быть позже начала.", reply_markup=res_admin_cancel_keyboard())
                return

        await update_promotion(promotion_id=promotion["id"], updated_fields={"end_date": new_end_date})
        promotion["end_date"] = new_end_date
        await state.update_data(promotion=promotion)
        await message.answer("Дата окончания обновлена.", reply_markup=res_admin_edit_promotion_keyboard())

        await state.set_state(PromotionEditForm.choosing_field)
    except ValueError:
        await message.answer("Неверный формат даты. Пример: 2025-07-06 15:30", reply_markup=res_admin_cancel_keyboard())


@RA_promotion_router.message(PromotionEditForm.waiting_for_url)
async def process_promotion_url(message: Message, state: FSMContext):
    new_url = message.text.strip()
    if not new_url:
        await message.answer("Ссылка не может быть пустой.")
        return
    if not URL_PATTERN.match(new_url):
        await message.answer("Неверный формат ссылки. Пожалуйста, введите корректную ссылку для участия:", reply_markup=res_admin_cancel_keyboard())
        return
    
    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        await message.answer("Ошибка доступа к мероприятию.")
        return

    await update_promotion(promotion_id=promotion["id"], updated_fields={"url": new_url})
    promotion["url"] = new_url
    await state.update_data(promotion=promotion)
    await message.answer("Ссылка обновлена.", reply_markup=res_admin_edit_promotion_keyboard())

    await state.set_state(PromotionEditForm.choosing_field)


@RA_promotion_router.message(PromotionEditForm.waiting_for_discount_or_bonus)
async def process_promotion_discount_or_bonus(message: Message, state: FSMContext):
    input_text = message.text.strip().lower()
    
    discount_match = DISCOUNT_PATTERN.match(input_text)
    bonus_match = BONUS_PATTERN.match(input_text)

    if discount_match:
        discount_value = float(discount_match.group(1))
        if discount_value <= 0 or discount_value > 100:
            await message.answer(
                "Значение скидки должно быть от 0 до 100%. Введите корректное значение, например 'Скидка 10%':",
                reply_markup=res_admin_cancel_keyboard()
            )
            return
        updated_fields = {"discount_or_bonus": "скидка", "discount_or_bonus_value": discount_value}
    elif bonus_match:
        bonus_value = float(bonus_match.group(1))
        if bonus_value <= 0:
            await message.answer(
                "Значение бонуса должно быть больше 0. Введите корректное значение, например 'Бонусов 500':",
                reply_markup=res_admin_cancel_keyboard()
            )
            return
        updated_fields = {"discount_or_bonus": "бонус", "discount_or_bonus_value": bonus_value}
    else:
        await message.answer(
            "Неверный формат. Введите 'Скидка 10%' или 'Бонусов 500':",
            reply_markup=res_admin_cancel_keyboard()
        )
        return

    data = await state.get_data()
    promotion = data.get("promotion")
    if not promotion:
        await message.answer("Ошибка доступа к акции.", reply_markup=res_admin_cancel_keyboard())
        await state.set_state(PromotionEditForm.choosing_field)
        return

    success = await update_promotion(promotion_id=promotion["id"], updated_fields=updated_fields)
    if success:
        promotion["discount_or_bonus"] = updated_fields["discount_or_bonus"]
        promotion["discount_or_bonus_value"] = updated_fields["discount_or_bonus_value"]
        await state.update_data(promotion=promotion)
        await message.answer(
            f"{updated_fields['discount_or_bonus'].capitalize()} обновлен: {updated_fields['discount_or_bonus_value']}{'%' if updated_fields['discount_or_bonus'] == 'скидка' else ''}",
            reply_markup=res_admin_edit_promotion_keyboard()
        )
    else:
        await message.answer(
            "Ошибка при обновлении скидки/бонуса. Попробуйте еще раз.",
            reply_markup=res_admin_edit_promotion_keyboard()
        )

    await state.set_state(PromotionEditForm.choosing_field)


async def delete_promotion(promotion_id: int) -> bool:
    url = f"{url_promotions}{promotion_id}/"
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(url, headers=headers) as resp:
                return resp.status in (200, 204)
    except Exception as e:
        logger.error(f"Failed to update promotion {promotion_id}: {e}")
        return False


@RA_promotion_router.message(F.text == "Удалить мероприятие")
async def delete_promotion_start(message: Message):
    promotions = await get_promotion_list()
    if not promotions:
        await message.answer("Нет доступных мероприятий для удаления")
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

# Хендлер для выбора мероприятия для удаления
@RA_promotion_router.message(F.text.startswith("❌ "))
async def delete_promotion_select(message: Message, state: FSMContext):
    promotion_title = message.text[2:].strip()
    promotion = await get_promotion_by_title(promotion_title)

    if not promotion:
        await message.answer("Не удалось найти акцию.")
        return

    await state.update_data(promotion=promotion)

    # Показываем информацию о мероприятии и кнопки для подтверждения удаления
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

    await message.answer_photo(
        caption=f"Вы выбрали акцию:\n\n{current_promotion_text}\n\nВы действительно хотите удалить эту акцию?",
        photo=promotion.get("photo", None),
        reply_markup=builder.as_markup(resize_keyboard=True)
    )

@RA_promotion_router.message(F.text == "Удалить")
async def confirm_delete_promotion(message: Message, state: FSMContext):
    data = await state.get_data()
    promotion = data.get("promotion")

    if not promotion:
        await message.answer("Ошибка: акция не найдена.")
        return

    success = await delete_promotion(promotion_id=promotion["id"])

    if success:
        await message.answer("Мероприятие успешно удалено.", reply_markup=res_admin_promotion_keyboard())
    else:
        await message.answer("Не удалось удалить мероприятие. Попробуйте снова.", reply_markup=res_admin_promotion_keyboard())

    await state.clear()