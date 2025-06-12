import logging
import re
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp

from client.keyboards.reply import main_kb
from data.config import config_settings
from data.url import url_loyalty, url_users

# Регулярные выражения для валидации
name_pattern = re.compile(r"^[А-Яа-яA-Za-zёЁ\-]{2,}$")
email_pattern = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$")
phone_pattern = re.compile(r"^\+?\d{10,15}$")

logger = logging.getLogger(__name__)

loyalty_router = Router()

# FSM состояния
class LoyaltyCardForm(StatesGroup):
    last_name = State()
    first_name = State()
    birth_date = State()
    phone_number = State()
    email = State()

# Запрос карты
async def fetch_loyalty_card(user_id: int):
    """Получает данные карты лояльности пользователя по его ID.

    Args:
        user_id (int): ID пользователя в Telegram.

    Returns:
        dict: Данные карты или None, если карта не найдена.

    Raises:
        RuntimeError: Если произошла ошибка при запросе.
    """
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    logger.info(f"Fetching loyalty card for user_id={user_id}")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(f"{url_loyalty}{user_id}/", headers=headers) as resp:
                if resp.status == 200:
                    card_data = await resp.json()
                    logger.info(f"Loyalty card fetched for user_id={user_id}")
                    return card_data
                elif resp.status == 404:
                    logger.info(f"No loyalty card found for user_id={user_id}")
                    return None
                else:
                    text = await resp.text()
                    logger.error(f"Failed to fetch loyalty card for user_id={user_id}: status={resp.status}, response={text}")
                    return None
    except Exception as e:
        logger.exception(f"Exception while fetching loyalty card for user_id={user_id}: {str(e)}")
        return None

# Обновление данных юзера
async def update_user_data(user_id: int, first_name: str, last_name: str, birth_date: str, phone_number: str,
                           email: str):
    """
    Обновление данных пользователя для карты лояльности
    """
    payload = {
        "user_first_name": first_name,
        "user_last_name": last_name,
        "birth_date": birth_date,
        "phone_number": phone_number,
        "email": email
    }
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    url = f"{url_users.rstrip('/')}/{user_id}/"
    logger.info(f"Updating user data for user_id={user_id} with payload={payload}, url={url}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.patch(url, json=payload, headers=headers) as resp:
                response_text = await resp.text()
                if resp.status in [200, 201]:
                    logger.info(f"User data updated for user_id={user_id}, status={resp.status}")
                    return True
                else:
                    logger.error(
                        f"Failed to update user data for user_id={user_id}: status={resp.status}, response={response_text}")
                    return False
    except aiohttp.ClientError as e:
        logger.exception(f"Client error while updating user data for user_id={user_id}: {str(e)}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error while updating user data for user_id={user_id}: {str(e)}")
        return False


# Создание карты
async def create_loyalty_card(user_id: int):
    """
    Создание карты лояльности
    """
    payload = {"user_id": user_id}
    headers = {"X-Bot-Api-Key": config_settings.BOT_API_KEY.get_secret_value()}
    logger.info(f"Creating loyalty card for user_id={user_id}")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(
                url=url_loyalty,
                json=payload,
                headers=headers
            ) as resp:
                text = await resp.text()
                if resp.status == 201:
                    card_data = await resp.json()
                    logger.info(f"Loyalty card created for user_id={user_id}, status={resp.status}")
                    return card_data
                elif resp.status == 400:
                    if "у вас уже есть карта" in text.lower():
                        logger.info(f"Loyalty card already exists for user_id={user_id}")
                        return None
                    logger.warning(f"Failed to create loyalty card for user_id={user_id}: {text}")
                    raise RuntimeError(f"Не удалось создать карту: {text}")
                else:
                    logger.error(f"Failed to create loyalty card for user_id={user_id}: status={resp.status}, response={text}")
                    raise RuntimeError(f"Ошибка сервера ({resp.status}): {text}")
    except Exception as e:
        logger.exception(f"Exception while creating loyalty card for user_id={user_id}: {str(e)}")
        raise RuntimeError(f"Произошла ошибка при создании карты: {str(e)}")

# Запуск процесса
@loyalty_router.message(F.text == "💳 Карта лояльности")
async def handle_loyalty_request(message: Message, state: FSMContext):
    """Обрабатывает запрос карты лояльности и запускает FSM при необходимости.

    Args:
        message (Message): Сообщение с запросом карты.
        state (FSMContext): Контекст состояния FSM для управления процессом.

    Notes:
        Проверяет наличие карты и запрашивает данные, если её нет.
    """
    user_id = message.from_user.id
    await state.clear()
    try:
        card = await fetch_loyalty_card(user_id)
        if card:
            card_image_url = card.get("card_image")
            if card_image_url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(card_image_url) as img_resp:
                        if img_resp.status == 200:
                            img_bytes = await img_resp.read()
                            image = BufferedInputFile(img_bytes, filename="loyalty_card.png")
                            logger.info(f"Sent loyalty card image for user_id={user_id}")
                            await message.answer_photo(photo=image, reply_markup=main_kb)
                            return
                        else:
                            logger.warning(f"Failed to fetch card image for user_id={user_id}, status={img_resp.status}")
            logger.warning(f"No card image available for user_id={user_id}")
            await message.answer(
                "Карта найдена, но изображение недоступно. Попробуйте позже или обратитесь в поддержку.",
                reply_markup=main_kb
            )
            return
        logger.info(f"Starting FSM for loyalty card creation for user_id={user_id}")
        await state.set_state(LoyaltyCardForm.last_name)
        await message.answer("Введите вашу фамилию:", reply_markup=main_kb)
    except Exception as e:
        logger.exception(f"Error processing loyalty card request for user_id={user_id}: {str(e)}")
        await message.answer(
            "Произошла ошибка при получении карты. Попробуйте позже или обратитесь в поддержку.",
            reply_markup=main_kb
        )

@loyalty_router.message(LoyaltyCardForm.last_name)
async def collect_last_name(message: Message, state: FSMContext):
    """Собирает фамилию пользователя для создания карты.

    Args:
        message (Message): Сообщение с фамилией.
        state (FSMContext): Контекст состояния FSM для сохранения данных.

    Notes:
        Проверяет формат фамилии и переключает состояние на first_name.
    """
    if not name_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Фамилия должна содержать только буквы и быть не короче 2 символов. Попробуйте снова:")
        return
    await state.update_data(last_name=message.text.strip())
    await state.set_state(LoyaltyCardForm.first_name)
    await message.answer("Введите ваше имя:")

@loyalty_router.message(LoyaltyCardForm.first_name)
async def collect_first_name(message: Message, state: FSMContext):
    """Собирает имя пользователя для создания карты.

    Args:
        message (Message): Сообщение с именем.
        state (FSMContext): Контекст состояния FSM для сохранения данных.

    Notes:
        Проверяет формат имени и переключает состояние на birth_date.
    """
    if not name_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Имя должно содержать только буквы и быть не короче 2 символов. Попробуйте снова:")
        return
    await state.update_data(first_name=message.text.strip())
    await state.set_state(LoyaltyCardForm.birth_date)
    await message.answer("Введите дату рождения (в формате ДД.ММ.ГГГГ):")

@loyalty_router.message(LoyaltyCardForm.birth_date)
async def collect_birth_date(message: Message, state: FSMContext):
    """Собирает дату рождения пользователя для создания карты.

    Args:
        message (Message): Сообщение с датой рождения.
        state (FSMContext): Контекст состояния FSM для сохранения данных.

    Notes:
        Проверяет формат (ДД.ММ.ГГГГ) и переключает состояние на phone_number.
    """
    try:
        birth_date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        birth_date_iso = birth_date_obj.date().isoformat()
    except ValueError:
        await message.answer("⚠️ Неверный формат. Попробуйте снова (ДД.ММ.ГГГГ):")
        return
    await state.update_data(birth_date=birth_date_iso)
    await state.set_state(LoyaltyCardForm.phone_number)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Введите ваш номер телефона или нажмите кнопку ниже:",
        reply_markup=keyboard
    )

@loyalty_router.message(LoyaltyCardForm.phone_number)
async def collect_phone_number(message: Message, state: FSMContext):
    """Собирает номер телефона пользователя для создания карты.

    Args:
        message (Message): Сообщение с номером телефона или контактом.
        state (FSMContext): Контекст состояния FSM для сохранения данных.

    Notes:
        Поддерживает ввод вручную или через кнопку "Поделиться номером".
    """
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text.strip().replace(" ", "")
    if not phone_pattern.fullmatch(phone):
        await message.answer(
            "⚠️ Введите корректный номер телефона (10–15 цифр, можно с '+'). Пример: +79001234567",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    await state.update_data(phone_number=phone)
    await state.set_state(LoyaltyCardForm.email)
    await message.answer(
        "Введите ваш email:",
        reply_markup=ReplyKeyboardRemove()
    )

@loyalty_router.message(LoyaltyCardForm.email)
async def collect_email_and_create(message: Message, state: FSMContext):
    """Собирает email и создаёт карту лояльности.

    Args:
        message (Message): Сообщение с email.
        state (FSMContext): Контекст состояния FSM для получения данных.

    Notes:
        Выполняет обновление данных пользователя и создание карты через API.
    """
    if not email_pattern.fullmatch(message.text.strip()):
        await message.answer("⚠️ Неверный формат email. Попробуйте снова:")
        return
    await state.update_data(email=message.text.strip())
    data = await state.get_data()
    user_id = message.from_user.id
    logger.info(f"Collected data for loyalty card creation for user_id={user_id}: {data}")
    try:
        # Обновляем данные пользователя
        updated = await update_user_data(
            user_id=user_id,
            first_name=data["first_name"],
            last_name=data["last_name"],
            birth_date=data["birth_date"],
            phone_number=data["phone_number"],
            email=data["email"]
        )
        if not updated:
            logger.error(f"Failed to update user data for user_id={user_id}")
            await message.answer(
                "Ошибка при сохранении данных. Попробуйте снова или обратитесь в поддержку.",
                reply_markup=main_kb
            )
            await state.clear()
            return

        # Создаем карту
        card = await create_loyalty_card(user_id)
        if card is None:
            card = await fetch_loyalty_card(user_id)
        if not card:
            logger.error(f"Failed to create or fetch loyalty card for user_id={user_id}")
            await message.answer(
                "Не удалось создать карту лояльности. Попробуйте позже или обратитесь в поддержку.",
                reply_markup=main_kb
            )
            await state.clear()
            return

        card_image_url = card.get("card_image")
        if not card_image_url:
            logger.warning(f"No card image available for user_id={user_id}")
            await message.answer(
                "Карта создана, но изображение отсутствует.",
                reply_markup=main_kb
            )
            await state.clear()
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(card_image_url) as img_resp:
                if img_resp.status == 200:
                    img_bytes = await img_resp.read()
                    image = BufferedInputFile(img_bytes, filename="loyalty_card.png")
                    logger.info(f"Sent loyalty card image for user_id={user_id}")
                    await message.answer_photo(photo=image, reply_markup=main_kb)
                else:
                    logger.warning(f"Failed to load card image for user_id={user_id}: status={img_resp.status}")
                    await message.answer(
                        "Карта создана, но не удалось загрузить изображение.",
                        reply_markup=main_kb
                    )
    except Exception as e:
        logger.exception(f"Error creating or loading loyalty card for user_id={user_id}: {str(e)}")
        await message.answer(
            "Произошла ошибка при обработке запроса. Попробуйте позже или обратитесь в поддержку.",
            reply_markup=main_kb
        )
    finally:
        await state.clear()